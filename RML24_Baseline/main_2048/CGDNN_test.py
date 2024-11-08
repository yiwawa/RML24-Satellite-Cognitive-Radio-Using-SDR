import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import h5py
import numpy as np
from tqdm import tqdm
import sys
import os
from torch.utils.tensorboard import SummaryWriter
from datetime import datetime
from Model.model_2048.CGDNN1D import CGDNN_1D
import random
def set_seed(seed_value):
    random.seed(seed_value)
    np.random.seed(seed_value)
    torch.manual_seed(seed_value)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed_value)
        torch.cuda.manual_seed_all(seed_value)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
set_seed(7)

class IQDataset(Dataset):
    def __init__(self, file_path):
        with h5py.File(file_path, 'r') as hdf:
            self.IQ_data = hdf['IQ_data'][:]
            self.class_ = hdf['class'][:]
            self.SNR = hdf['snr'][:]
    def __len__(self):
        return len(self.IQ_data)
    def __getitem__(self, idx):
        iq_data = self.IQ_data[idx]
        label = self.class_[idx]
        snr = self.SNR[idx]
        iq_data = iq_data.transpose()
        return iq_data, label, snr

def main():
    device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")
    print("using {} device.".format(device))
    current_time = datetime.now().strftime('%b%d_%H-%M-%S')
    writer = SummaryWriter(log_dir=f'runs/CGDNN_2048/{current_time}')

    # load data
    file_path = '../data/TSML_GNU_2048.h5'  ######## TODO
    dataset = IQDataset(file_path)

    train_size = int(0.6 * len(dataset))
    val_size = int(0.2 * len(dataset))
    test_size = len(dataset) - train_size - val_size
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, val_size, test_size])


    batch_size = 128    # TODO

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True )
    validate_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    print("using {} samples for training, {} samples for validation.".format(train_size, val_size))

    num_classes = 22  # TODO
    seq_length = 2048 # TODO
    net = CGDNN_1D(num_classes=num_classes)
    net.to(device)

    loss_function = nn.CrossEntropyLoss()
    optimizer = optim.Adam(net.parameters(), lr=0.0001)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 3, 0.1)

    epochs = 50
    save_path = '../result/2048/CGDNN1D_2048.pth'   # TODO
    best_acc = 0.0

    #train
    for epoch in range(epochs):
        net.train()
        running_loss = 0.0
        running_corrects = 0
        for inputs, labels, snrs in tqdm(train_loader):
            inputs = inputs.type(torch.FloatTensor).to(device)
            labels = labels.long().to(device)
            optimizer.zero_grad()
            outputs = net(inputs)
            loss = loss_function(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, preds = torch.max(outputs, 1)
            running_corrects += torch.sum(preds == labels.data)

        epoch_loss = running_loss / len(train_loader.dataset)
        epoch_acc = running_corrects.double() / len(train_loader.dataset)

        # Record training loss and accuracy
        writer.add_scalar('training loss', epoch_loss, epoch)
        writer.add_scalar('training accuracy', epoch_acc, epoch)
        # print
        print('epoch: {}, train_loss: {:.4f}, train_acc: {:.4f}'.format(epoch, epoch_loss, epoch_acc))

        # Validation
        net.eval()
        running_loss = 0.0
        running_corrects = 0
        with torch.no_grad():
            for inputs, labels, snrs in tqdm(validate_loader):
                inputs = inputs.type(torch.FloatTensor).to(device)
                labels = labels.long().to(device)
                outputs = net(inputs)
                loss = loss_function(outputs, labels)

                running_loss += loss.item()
                _, preds = torch.max(outputs, 1)
                running_corrects += torch.sum(preds == labels.data)

        epoch_loss = running_loss / len(validate_loader.dataset)
        epoch_acc = running_corrects.double() / len(validate_loader.dataset)

        # Record validation loss and accuracy
        writer.add_scalar('validation loss', epoch_loss, epoch)
        writer.add_scalar('validation accuracy', epoch_acc, epoch)
        # print
        print('epoch: {}, validate_loss: {:.4f}, validate_acc: {:.4f}'.format(epoch, epoch_loss, epoch_acc))
        scheduler.step()

        if epoch_acc > best_acc:
            best_acc = epoch_acc
            torch.save(net.state_dict(), save_path)
            print('Find better model in epoch {}, saving model.bestacc {}'.format(epoch, best_acc))

    writer.close()
    print('Finished Training')

    return

if __name__ == '__main__':
    main()
