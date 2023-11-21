import numpy as np
import torch
from torch import nn
from torch.autograd import Variable
# Function for cpu or gpu assignment

def to_var(X, CalInGPU):
    if CalInGPU and torch.cuda.is_available():
        X = X.cuda()
    return Variable(X)

def get_row_col_indices(matrix):
    # Get dimensions of matrix
    n1, n2 = matrix.shape
    
    # First Column wise
    indices_col = [np.where(matrix[:, i] == 1)[0] for i in range(n2)]

    # Now Row wise
    indices_row = [np.where(matrix[i, :] == 1)[0] for i in range(n1)]

    return indices_col, indices_row
    
class HuberCell(nn.Module):
    # Constructor initalizes all the parameters that were passed to it from the unfolded net. Note: v, neta, lamda1/2, S are different for each layer. coef_gamma is constant
    def __init__(self, c, lamda, mu, delta, tau, CalInGPU, layer):
        super(HuberCell,self).__init__()
        
        self.layer = layer

        self.c = (c)
        self.lamda = (lamda)
        self.mu = (mu)

        self.delta = (delta)
        self.tau = (tau)
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        self.CalInGPU = CalInGPU
        self.relu = nn.ReLU()
        self.sig = nn.Sigmoid()



    # Forward Pass recieves a list of 3 elements, data tensor of shape (2, 160, 320), a mask of shape (160, 320) which is True wherever there is
    # missing value in the matrix at index data[0], and rank of lowrank matrix

    def forward(self, lst):
        X_Omega, smapling_mat, rank = lst[0], lst[1], lst[2]
        r, c = X_Omega.shape
        self.U = torch.rand((r, rank)) 
        self.V = U.torch.rand((rank, c))

        # Get the lowrank and the L matrix which is for now (49, 60) zeros
        input = data[0]
        L = data[1]

        # get the dimension and the parameters
        H, U = input.shape
        th_incomplete_tau = self.sig(self.v) * self.coef_gamma
        th_neta = self.neta
        th_lamda1 =  self.lamda1
        th_lamda2 =  self.lamda2
        th_rho = self.rho
        th_S = self.S
        coef_gamma = self.coef_gamma

        # Get Q_tilda which is the diagonal of the flattened Q - sampling matrix
        Q = entries_mask.view(H, U).float()
        Q_tilda = torch.diag(Q.view(Q.shape[0] * Q.shape[1]))

        # Get S_tilda which is the kronecker product of I_N identity matrix (where N is 60) and S*S
        S_tilda = torch.kron(torch.eye(U, device = torch.device(self.device), requires_grad = self.CalInGPU), torch.matmul(th_S.T, th_S))

        # The Reconstruction Layer - Eq (12 in original paper)
        # Second half of equation - L is Z in the paper
        vec = th_rho * (L.view(H, U) - th_P.view(H, U)) + torch.where(entries_mask.view(H, U), input.view(H, U), 0)
        # First half of equation
        Xtmp1 = torch.linalg.inv(Q_tilda + th_lamda1 * D_tilda + th_lamda2 * S_tilda + th_rho * torch.eye(H * U, device = torch.device(self.device), requires_grad = self.CalInGPU))
        # Combining the two
        Xtmp = Xtmp1 @ vec.view(H * U)

        # The Non-Linear Transform Layer - Eq (13 in original paper)
        Ltmp = self.svtC(Xtmp.view(H, U) + th_P.view(H, U), th_incomplete_tau)

        # The Multiplier Update Layer - Eq (14 in original paper)
        Ptmp = th_P.view(H, U) + th_neta * (Xtmp.view(H, U) - Ltmp.view(H, U))

        # Update data tensor with the reconstructed prediction and return the list. The list gets passed to the next ISTA cell and then after all layers returns the list.
        data[1] = Ltmp.view(H, U)
        return [data, entries_mask, D_tilda, Ptmp.view(H,U)]

class UnfoldedNet_Huber(nn.Module):
    def __init__(self, params = None, model_denoise = None):
        super(UnfoldedNet_Huber, self).__init__()
        
        # Constructor initializes various parameters from the given parameter dictionary
        self.layers = params['layers']
        self.CalInGPU = params['CalInGPU']
        
        self.n1, self.n2 = params['size1'], params['size2']
        self.rank = params['rank']
        
        self.model_denoise = model_denoise

        self.rank = params['rank']

        self.c = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_c'], self.CalInGPU)
        self.initial_lamda = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_lamda'], self.CalInGPU)
        self.initial_sigma = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_sigma'], self.CalInGPU)
        self.initial_mu = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_mu'], self.CalInGPU)
        self.initial_delta = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_delta'], self.CalInGPU)
        self.initial_tau = to_var(torch.ones(self.layers, requires_grad = True) * params['initial_tau'], self.CalInGPU)

        # For matrix if needed
        # self.S = to_var(torch.ones((self.layers, params['size1'], params['size1']), requires_grad = True) * params['initial_S'], self.CalInGPU, True)
        # self.y1 = nn.Parameter(to_var(torch.ones((params['size1'], params['size2']), requires_grad = True) * params['initial_y1'], self.CalInGPU))

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.sig = nn.Sigmoid()
        self.relu = nn.ReLU()

        self.model = self.makelayers()

    # Function which intializes num_layers ISTA cells by passing it those parameters that are learnt per layer like lambda1/2, neta, S and those that are fixed like coef_gamma
    def makelayers(self):
        filt = []
        for layer_idx in range(1, self.layers + 1):
          if layer_idx % 2 != 0: # --> V Update Layer
              
          pass

    # Forward Pass recieves the lowrank noisy matrix
    def forward(self, x):
                
        self.U = torch.ones(self.n1, self.rank)
        self.V = torch.ones(self.rank, self.n2)

        # Now initalize the neural architecture of even number of layers where even numbered layers correspond to updating U and odd numbered
        # layers correspond to updating V. Each odd numbered layers will have number of nodes equal to number of rows and each even numbered 
        # column will have number of nodes equal to the number of columns. Each node in layer is connected to a huber cell of certain number of
        # iterations and each huber cell in each layer will have same initalization of parameters at start. 

        # We intialize a tensor 'data' of shape (2, 160, 320) and assign the first index of it with the lowrank component passed i.e. first element of x
        data = to_var(torch.zeros([2] + list(x[0].shape)), self.CalInGPU)
        data[0] = x[0]

        # Get the dimensions i.e. H = 160, U = 320 and then intialize a sampling matrix of shape (160, 320) which is True wherever there is a missing value in x/L
        H, U = x[0].shape
        entries_mask = (torch.isnan(data[0]))
        # entries_mask = (data[0] != 0)
        
        # Pass the lowrank component to the denoised_autoencode model
        x_reconstructed = self.model_denoise.forward(x_reconstructed)
        
        data[0] = x_reconstructed

        # Then forward pass to the Huber cell, the data tensor, the mask rank
        ans = self.filter([data, entries_mask, self.rank]) # X_Omega --> X_tilda --> UV_tilda --> 
        data = ans[0] 
        return ans

    def getexp_LS(self):
        neta = self.neta
        lamda1 = self.lamda1
        lamda2 = self.lamda2

        v = self.v
        S = self.S
        rho = self.rho
        
        coef_gamma = self.coef_gamma
        # exp_tau used for svt threshold of Z/X (eq 13 of original paper)
        exp_tau = self.sig(v) * coef_gamma

        if torch.cuda.is_available():
          neta = neta.cpu().detach().numpy()
          v = v.cpu().detach().numpy()
          lamda1 = lamda1.cpu().detach().numpy()
          lamda2 = lamda2.cpu().detach().numpy()
          S = S.cpu().detach().numpy()
          rho = rho.cpu().detach().numpy()
          coef_gamma = coef_gamma.cpu().detach().numpy()
          exp_tau = exp_tau.cpu().detach().numpy()
        else:
          neta = neta.detach().numpy()
          v = v.detach().numpy()
          lamda1 = lamda1.detach().numpy()
          lamda2 = lamda2.detach().numpy()
          S = S.detach().numpy()
          rho = rho.detach().numpy()
          coef_gamma = coef_gamma.detach().numpy()
          exp_tau = exp_tau.detach().numpy()
        return neta, v, lamda1, lamda2, S, rho, coef_gamma, exp_tau
