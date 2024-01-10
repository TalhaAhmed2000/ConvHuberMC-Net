import torch

# try:
#     import hubermc, dataset_processing, logs_and_results, training
# except ImportError:
#     print("[INFO] Cloning the repository and importing convmc & dataset_preprocessing script...")
#     subprocess.run(["git", "clone", "https://github.com/Talha-Nehal-Undegrad-Study/ConvHuberMC-Net.git"])
#     subprocess.run(["mv", "ConvHuberMC-Net/python_scripts", "py_scripts"])
#     sys.path.append('py_scripts')
#     import hubermc, dataset_processing, logs_and_results, training

from python_scripts import architecture

def get_hyperparameter_grid(Model, TrainInstances, ValInstances, BatchSize, ValBatchSize, num_epochs, learning_rate):
  hyper_param = {}

  hyper_param['Model'] = Model
  hyper_param['TrainInstances'] = TrainInstances
  hyper_param['ValInstances'] = ValInstances
  hyper_param['BatchSize'] = BatchSize
  hyper_param['ValBatchSize'] = ValBatchSize
  hyper_param['Epochs'] = num_epochs
  hyper_param['Lr'] = learning_rate

  return hyper_param

# Defining a fucntion for loading/instantiating the model based on some boolean values and updates log
def get_model(params_net, hyper_param_net, log, path_whole = None, path_dict = None, loadmodel = False, load_frm = None):
    
    # Construct Model
    print('Configuring Network...\n')
    log.write('Configuring network...\n')

    if not loadmodel:
        print('Instantiating Model...\n')
        log.write('Instantiating Model...\n')
        if hyper_param_net['Model'] == 'HuberMC-Net':
            net = architecture.UnfoldedNet_Huber(params_net)
            print('Model Instantiated...\n')
            log.write('Model Instantiated...\n')

    else:
        print('Loading Model...\n')
        log.write('Loading Model...\n')
        if hyper_param_net['Model'] == 'HuberMC-Net':
            if load_frm == 'state_dict':
                net = architecture.UnfoldedNet_Huber(params_net)
                state_dict = torch.load(path_dict, map_location = 'cpu')
                net.load_state_dict(state_dict)
                print('Model loaded from state dict...\n')
                log.write('Model loaded from state dict...\n')
            elif load_frm == 'whole_model':
                net = torch.load(path_whole)
                print('Whole model loaded...\n')
                log.write('Whole model loaded...\n')
            net.eval()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    net = net.to(device)

    return net

# Training functions and Plotting Functions

def train_step(model, dataloader, loss_fn, optimizer, CalInGPU, TrainInstances, batch, inference = False):
  # Put model in train mode
  model.train()

  # Initalize loss for lowrank matrices which will be calculated per batch for each epoch
  loss_mean = 0
  loss_lowrank_mean = 0

  for _, (D, L) in enumerate(dataloader):
    # set the gradients to zero at the beginning of each epoch
    optimizer.zero_grad()
    with torch.autograd.set_detect_anomaly(True):
        for mat in range(batch):
            inputs = architecture.to_var(D[mat], CalInGPU)
            targets_L = architecture.to_var(L[mat], CalInGPU)
            # Forward + backward + loss
            outputs_L = model(inputs)
            # Current loss
            loss = (loss_fn(outputs_L, targets_L))/torch.square(torch.norm(targets_L, p = 'fro'))
            loss_lowrank = (loss_fn(outputs_L,targets_L))/torch.square(torch.norm(targets_L, p = 'fro'))
            loss_mean += loss.item()
            loss_lowrank_mean += loss_lowrank.item()
            if not inference:
              loss.backward()
    if not inference:
        optimizer.step()
  loss_mean = loss_mean/TrainInstances
  loss_lowrank_mean = loss_lowrank_mean/TrainInstances

  return loss_mean, loss_lowrank_mean

def test_step(model, dataloader, loss_fn, CalInGPU, ValInstances, batch):

  model.eval()
  loss_val_mean, loss_val_lowrank_mean = 0, 0

  # Validation
  with torch.no_grad():
    for _, (D, L) in enumerate(dataloader):
      for mat in range(batch):
        inputs = architecture.to_var(D[mat], CalInGPU)   # "mat"th picture
        targets_L = architecture.to_var(L[mat], CalInGPU)
        outputs = model(inputs)  # Forward
        # Current loss
        loss_val = loss_fn(outputs, targets_L)/torch.square(torch.norm(targets_L, p = 'fro'))
        loss_val_lowrank = loss_fn(outputs, targets_L)/torch.square(torch.norm(targets_L, p = 'fro'))
        loss_val_mean += loss_val.item()
        loss_val_lowrank_mean += loss_val_lowrank.item()

  loss_val_mean = loss_val_mean/ValInstances
  loss_val_lowrank_mean = loss_val_lowrank_mean/ValInstances

  return loss_val_mean, loss_val_lowrank_mean
