import numpy as np
import theano
import h5py
from theano import tensor
from blocks import roles
from blocks.model import Model
from blocks.extensions import saveload
from blocks.filter import VariableFilter
from utils import MainLoop
from config import config
from model import nn_fprop
from utils import get_stream
import argparse
import sys
import os
import pandas as pd
import time
import signal
from pandas.parser import CParserError
import matplotlib.pyplot as plt
from fuel.datasets import H5PYDataset
from matplotlib.widgets import Button

locals().update(config)

def my_longitude(ndarray):
    return map(lambda x: (x - 2) / 7 - 73.915, ndarray)

def my_latitude(ndarray):
    return map(lambda x: (x - 2) / 7 + 40.76, ndarray)


def sample(x_curr, fprop):

    hiddens = fprop(x_curr)
    #print x_curr.shape
    #print x_curr[-1:,:,:]
    probs = hiddens.pop().astype(theano.config.floatX)
    # probs = probs[-1,-1].astype('float32')
    #print "the output shape is: "
    #print probs.shape
    #print "getting the last element..."
    #probs = probs[-1,:].astype('float32')
    #print probs
    #print probs.shape
    #print my_longitude(probs[0])
    #print my_latitude(probs[1])
    #hierarchy_values = [None] * (len(predict_funcs) + 1)
    # probs = probs / probs.sum()
    # sample = np.random.multinomial(1, probs).nonzero()[0][0]
    # print(sample)
    return probs, hiddens


if __name__ == '__main__':
    # Load config parameters
    locals().update(config)
    float_formatter = lambda x: "%.5f" % x
    np.set_printoptions(formatter={'float_kind':float_formatter})
    parser = argparse.ArgumentParser(
        description='Generate the learned trajectory',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    args = parser.parse_args()

    print('Loading model from {0}...'.format(save_path[network_mode]))

    x = tensor.tensor3('features', dtype=theano.config.floatX)
    y = tensor.tensor3('targets', dtype=theano.config.floatX)
    out_size = len(output_columns)
    in_size = len(input_columns)

    cost, mu, sigma, mixing, output_hiddens, mu_linear, sigma_linear, mixing_linear, cells = nn_fprop(x, y, in_size, out_size, hidden_size[network_mode], num_layers, layer_models[network_mode], 'MDN', training=False)
    main_loop = MainLoop(algorithm=None, data_stream=None, model=Model(cost),
                         extensions=[saveload.Load(save_path[network_mode])])

    for extension in main_loop.extensions:
        extension.main_loop = main_loop
    main_loop._run_extensions('before_training')
    bin_model = main_loop.model
    print 'Model loaded. Building prediction function...'
    hiddens = []
    initials = []

    for i in range(num_layers):
        brick = [b for b in bin_model.get_top_bricks() if b.name == layer_models[network_mode][i] + str(i) + '-'][0]
        hiddens.extend(VariableFilter(theano_name=brick.name + '_apply_states')(bin_model.variables))
        hiddens.extend(VariableFilter(theano_name=brick.name + '_apply_cells')(cells))
        initials.extend(VariableFilter(roles=[roles.INITIAL_STATE])(brick.parameters))

    fprop = theano.function([x], hiddens + [mu])

    #predicted = np.array([1,1], dtype=theano.config.floatX)
    #x_curr = [[predicted]]

    #print(x[2].eval())
    file = h5py.File(hdf5_file[network_mode], 'r')
    input_dataset = file['features']  # input_dataset.shape is (8928, 200, 2)
    input_dataset = np.swapaxes(input_dataset,0,1)
    print input_dataset.shape

    output_mu = np.empty((100, 2, 100), dtype='float32')

    #sample_results = sample([x], fprop, [component_mean])
    #x_curr = [input_dataset[0,:,:]]

    for i in range(100):
        x_curr = input_dataset[:,i:i+1,:]
        #print x_curr
        test, newinitials = sample(x_curr, fprop)  # the shape of input_sec_network is (200,)
        ############  make data for the second network ########################
        #print input_helper[i].shape
        #input_helper[i] = input_sec_network

        test = test[-1]
        print test.shape
        test[0] = my_longitude(test[0])
        test[1] = my_latitude(test[1])
        output_mu[i, 0, :] = test[0]
        output_mu[i, 1, :] = test[1]
        # for initial, newinitial in zip(initials, newinitials):
        #    initial.set_value(newinitial[-1].flatten())
           #print newinitial[-1].flatten()

##############################################
#############  Plotting  #####################
index = 0
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.2)

longitude = input_dataset[:, index, 0]
original_longitude = my_longitude(longitude[longitude > 0])

latitude = input_dataset[:, index, 1]
original_latitude = my_latitude(latitude[latitude > 0])
#
#
l1, = plt.plot(original_longitude, original_latitude, 'bo')
#
#plt.axis([-74.06, -73.77, 40.61, 40.91])
l2, = plt.plot(output_mu[index, 0, :], output_mu[index, 1, :], 'ro')



class Index(object):
    index = 0

    def next(self, event):
        self.index += 1
        #plt.plot(output_mu[self.index, 0, :], output_mu[self.index, 1, :], 'ro')

        longitude = input_dataset[:, self.index, 0]
        original_longitude = my_longitude(longitude[longitude > 0])

        latitude = input_dataset[:, self.index, 1]
        original_latitude = my_latitude(latitude[latitude > 0])

        l1.set_xdata(original_longitude)
        l1.set_ydata(original_latitude)

        l2.set_xdata(output_mu[self.index, 0, :])
        l2.set_ydata(output_mu[self.index, 1, :])
        plt.draw()

callback = Index()
axnext = plt.axes([0.81, 0.05, 0.1, 0.075])
bnext = Button(axnext, 'Next')
bnext.on_clicked(callback.next)
plt.show()