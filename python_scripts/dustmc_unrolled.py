import torch
import torch.nn as nn
import torch.nn.functional as F

from torch.autograd import Variable
from scipy.fftpack import dct

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

def to_var(X, CalInGPU):
    if CalInGPU and torch.cuda.is_available():
        X = X.to('cuda')
    else:
        X = X.to('cpu')
    return Variable(X)

# Soft Thresholding Function
def soft_thresholding(thres, mat):
    """
    Apply soft thresholding to each column of the matrix mat with threshold thres.
    
    Args:
    mat (torch.Tensor): Input matrix (shape: [d, T])
    thres (float): Threshold value
    
    Returns:
    torch.Tensor: Matrix after applying soft thresholding column-wise
    """
    return torch.sign(mat) * torch.maximum(torch.zeros_like(mat), torch.abs(mat) - thres)

# Compute Attention Map Function
def compute_attention_map(H, D):
    """
    Computes the attention map for the given token vectors and matrix D.
    
    Parameters:
    - H: A 2D array of token vectors (shape: [d, T])
    - D: A matrix (shape: [n, d])
    
    Returns:
    - A 2D array representing the attention map (shape: [T, T])
    """
    
    # Transpose H to shape (T, d)
    H_T = H.T  # Now H_T is (T, d)
    
    # Compute βi values
    DH = D @ H_T.T  # Shape of DH (n, T)
    # beta_i = torch.exp(-0.5 * torch.sum(DH ** 2, dim = 0))  # Shape (T,)
    
    # Number of tokens
    T = H_T.shape[0]
    
    # Initialize the attention map
    attention_map = torch.zeros((T, T), device = H.device)
    attention_map = torch.softmax(H_T @ D.T @ D @ H_T.T, dim = -1) # column wise softmax
    
    # Compute the attention weights
    # for t in range(T):
    #     ht = H_T[t]  # Shape (d,)
    #     ht_DTD = ht @ (D.T @ D)  # Precompute ht @ (D.T @ D) for efficiency
    #     exp_terms = torch.exp(ht_DTD @ H_T.T)  # Shape (T,)
    #     numerator = exp_terms  # Shape (T,)
    #     denominator = torch.sum(numerator)  # Sum all elements to get the denominator
    #     attention_map[t, :] = numerator / denominator  # Assign the row of attention_map
    
    return attention_map

# LISTA Class
class LISTA(nn.Module):
    def __init__(self, d, c, D, A):
        super(LISTA, self).__init__()
        self.U = nn.Parameter(torch.eye(d) - (1 / c) * D.T @ A.T @ A @ D) # (d, d)
        self.V = nn.Parameter((1 / c) * D.T @ A.T) # (d, m)
        self.c = c

    def forward(self, X, Z, l1):
        # print(self.U.shape, Z.shape, self.V.shape, X.shape)
        mat = self.U @ Z + self.V @ X
        thres = l1 / self.c
        H_star = soft_thresholding(thres, mat)
        return H_star

# Self Attention Class
class SelfAttention(nn.Module):
    def __init__(self):
        super(SelfAttention, self).__init__()
        # self.layer_norm = nn.LayerNorm(normalized_shape, elementwise_affine=True)  # Define layer normalization here if needed

    def forward(self, H, D, l2):
        attn_map = compute_attention_map(H, D)
        # print(H.shape, D.shape, attn_map.shape)
        Z = l2 * H @ attn_map
        return Z

# Blue Box Layer Class
class BlueBoxLayer(nn.Module):
    def __init__(self, d, c, D, A):
        super(BlueBoxLayer, self).__init__()
        self.self_attention = SelfAttention()
        self.lista = LISTA(d, c, D, A)

    def forward(self, H, D, l2, X, l1, c):
        Z = self.self_attention(H, D, l2)
        H = self.lista(X, Z, l1)
        return H

# DustNet Class
class DustNet(nn.Module):
    def __init__(self, hyper_param_net):
        super(DustNet, self).__init__()
        self.K = hyper_param_net['K']
        self.mu = hyper_param_net['mu']
        self.sigma = hyper_param_net['sigma']
        self.m = hyper_param_net['m']
        self.n = hyper_param_net['n']
        self.d = hyper_param_net['d']
        self.T = hyper_param_net['T']
        # self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Learnable parameters
        self.A = nn.Parameter(torch.rand(self.m, self.n, device = DEVICE))
        D_init = torch.randn(self.n, self.d, device = DEVICE)
        # Apply DCT to the matrix
        D_dct = dct(D_init.numpy(), type = 2, norm = 'ortho')

        # Convert the DCT result back to a torch tensor and make it a learnable parameter
        self.D = nn.Parameter(torch.tensor(D_dct, device = DEVICE, dtype = torch.float32))  # Replace DCT initialization with random initialization for simplicity
        self.l1 = nn.Parameter(torch.randn(1, device = DEVICE))
        self.l2 = nn.Parameter(torch.randn(1, device = DEVICE))
        self.c = nn.Parameter(torch.randn(1, device = DEVICE))
        self.H = torch.zeros((self.d, self.T), device = DEVICE)

        # Blue box layers
        self.blue_box_layers = nn.ModuleList([BlueBoxLayer(self.d, self.c, self.D, self.A) for _ in range(self.K)])

    def forward(self, S):
        # print(S.shape)
        assert S.shape == (self.n, self.T), f'S.shape should be {(self.n, self.T)}, but is {S.shape}.'
        
        temp = self.A @ S
        # print(f'temp: {temp}')
        # For GMM we will generate freshly array_Omega and then use similar process (line 57 - 63 in generate_synthetic_data.py) to get its corrupted entry
        E = (torch.randn_like(temp) * self.sigma + self.mu)
        # print(f'E: {E}')
        
        X = temp + E # (m, T)
        # print(self.A.shape, S.shape)
        # print(f'X: {X}')
        
        for layer in self.blue_box_layers:
            H = layer(self.H, self.D, self.l2, X, self.l1, self.c)
        
        S_star = self.D @ H
        return S_star

# Example usage:
# d, m, n, T, K, mu, sigma are hyperparameters
# model = DustNet(K=5, mu=0, sigma=1, m=3, n=3, d=3, T=10)
# S = torch.randn(n, T)
# output = model(S)
# print(output)
