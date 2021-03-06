#!/usr/bin/env python
# coding=utf-8
import os
import json
import os.path as osp
import numpy as np
import random
import collections
import torch
import torchvision
import cv2
from torch.utils import data 
from PIL import Image as PILImage
import scipy.io as sio
#alpha,beta = 0.6976,10.5909
alpha,beta = 0.7132, 9.98
K=80.0
def get_depth_sid(depth_labels):
    if torch.cuda.is_available():
        alpha_ = torch.tensor(alpha).cuda()
        beta_ = torch.tensor(beta).cuda()
        K_ = torch.tensor(K).cuda()
   
    else:
        alpha_ = torch.tensor(alpha)
        beta_ = torch.tensor(beta)
        K_ = torch.tensor(K)

    t = torch.exp(torch.log(alpha_) + torch.log(beta_ / alpha_) * (depth_labels) / K_)
    depth = t
    return depth
class LIPParsingEdgeDataSet(data.Dataset):
    def __init__(self, root, list_path, max_iters=None, crop_size=(473, 473), mean=(128, 128, 128), scale=False, mirror=True, ignore_label=255):
        self.root = root
        self.list_path = list_path
        self.crop_h, self.crop_w = crop_size
        self.resize_h, self.resize_w = (288,384)
        self.scale = scale
        self.ignore_label = ignore_label
        self.mean = mean
        self.is_mirror = mirror 
        
        self.img_ids = [i_id.strip() for i_id in open(list_path)]
        if not max_iters==None:
            self.tot_len = max_iters
            #self.img_ids = self.img_ids * int(np.ceil(float(max_iters) / len(self.img_ids))) 
                
        self.files = []
         
        for item in self.img_ids:
           # image_path, label_path, label_rev_path, edge_path = item
            image_path = item
            label_path = item.replace('rgb','dep')
            label_path = label_path.replace('png','mat')
            name = osp.splitext(osp.basename(label_path))[0]  
            img_file = osp.join(self.root, image_path)
            label_file = osp.join(self.root, label_path) 
            self.files.append({
                "img": img_file,
                "label": label_file,
                "name": name
            })
          
    def get_depth_sid(self, depth):
       # print(np.log(depth/alpha))
       # print(np.log(beta/alpha))
        mask = (depth>0) &(depth<alpha)
        k = K * np.log(depth / alpha) / np.log(beta / alpha)
       # k[mask]=0
        k = k.astype(np.int32)
       # print(k,'k')
        return k
    def __len__(self):
        #return len(self.files)
        return self.tot_len
    def generate_scale_label(self, image, label):
        img_h, img_w = label.shape 
        f_scale = min(self.crop_h / float(img_h), self.crop_w / float(img_w)) 
        f_scale *= (0.7 + random.randint(0, 6) / 10.0)
        image = cv2.resize(image, None, fx=f_scale, fy=f_scale, interpolation = cv2.INTER_LINEAR)
        img_h, img_w, _ = image.shape 
        
        label = np.resize(label,(img_h, img_w))
         
        return image, label
     
    def __getitem__(self, index):
        index = random.randint(0,len(self.img_ids)-1) 
        datafiles = self.files[index]
          
        name = datafiles["name"]  
         
        image = cv2.imread(datafiles["img"], cv2.IMREAD_COLOR)
        label = sio.loadmat(datafiles['label'])['depthOut']
        label_ori = sio.loadmat(datafiles['label'])['depthOut']
# label_rev = cv2.imread(datafiles["label_rev"], cv2.IMREAD_GRAYSCALE)
        try:
            size = image.shape 
        except:
            print(datafiles["img"])
            print(image)
        if self.is_mirror:
            flip = np.random.choice(2) * 2 - 1

            image = image[:, ::flip, :] 
            label = label[:, ::flip]
        #if np.max(label) > 20:
        #    print('labelsmirror',np.max(label))
        if self.scale:
            image, label = self.generate_scale_label(image, label)
        
        image = cv2.resize(image,(self.resize_w,self.resize_h), interpolation = cv2.INTER_LINEAR)
       # print(image.shape) 
        label = cv2.resize(label,(self.resize_w, self.resize_h))
        label = np.asarray(label, np.float32)
        image = np.asarray(image, np.float32)
        image -= self.mean
        
        image_cropped = np.zeros((self.crop_h, self.crop_w, 3), dtype=np.float32)
        label_cropped = np.zeros((self.crop_h, self.crop_w), dtype=np.float32)
        img_h, img_w = label.shape
        pad_h = max(img_h-self.crop_h , 0)
        pad_w = max(img_w-self.crop_w , 0)
       # print(img_w) 
       # print(self.crop_w) 
        h_off = random.randint(0, pad_h)
        w_off = random.randint(0, pad_w) 
        image_cropped = image[h_off:h_off+self.crop_h, w_off:w_off+self.crop_w]
        label_cropped = label[h_off:h_off+self.crop_h, w_off:w_off+self.crop_w]
       # print(image_cropped.shape)        
        #if pad_h > 0 or pad_w > 0:
        #    img_pad = cv2.copyMakeBorder(image, 0, pad_h, 0, 
        #        pad_w, cv2.BORDER_CONSTANT, 
        #        value=(0.0, 0.0, 0.0))
        #    label_pad = cv2.copyMakeBorder(label, 0, pad_h, 0, 
        #        pad_w, cv2.BORDER_CONSTANT,
        #        value=(self.ignore_label,))
        #    edge_pad = cv2.copyMakeBorder(edge, 0, pad_h, 0, 
        #        pad_w, cv2.BORDER_CONSTANT,
        #        value=(0.0,))
        #else:
        #    img_pad, label_pad, edge_pad = image, label, edge

        #img_h, img_w = label_pad.shape
        #h_off = random.randint(0, img_h - self.crop_h)
        #w_off = random.randint(0, img_w - self.crop_w) 
        #image = np.asarray(img_pad[h_off : h_off+self.crop_h, w_off : w_off+self.crop_w], np.float32)
        #label = np.asarray(label_pad[h_off : h_off+self.crop_h, w_off : w_off+self.crop_w], np.float32)
        #edge = np.asarray(edge_pad[h_off : h_off+self.crop_h, w_off : w_off+self.crop_w], np.float32)
       
        
        image = image_cropped.transpose((2, 0, 1))
        #print(image.shape)
        return image.copy(), self.get_depth_sid(label_cropped.copy()),  np.array(size), name    
  
class LIPDataValSet(data.Dataset):
    def __init__(self, root, list_path, crop_size=(544, 409), mean=(128, 128, 128)):
        self.root = root 
        self.list_path = list_path
        self.crop_h, self.crop_w = crop_size
        self.mean = mean
        self.resize_h, self.resize_w = (288,384)
         
        self.img_ids = [i_id.strip().split() for i_id in open(list_path)]
        self.files = [] 

        for item in self.img_ids:
           # image_path, label_path, label_rev_path, edge_path = item
            image_path = item[0]
            label_path = item[0].replace('png','mat')
            name = osp.splitext(label_path)[0]  
            img_file = osp.join(self.root, 'test_rgb',image_path)
            label_file = osp.join(self.root, 'test_depth',label_path) 
            self.files.append({
                "img": img_file,
                "label": label_file,
                "name": name
            })
    def generate_scale_image(self, image, f_scale): 
        image = cv2.resize(image, None, fx=f_scale, fy=f_scale, interpolation = cv2.INTER_LINEAR) 
        return image
    
    def resize_image(self, image, size): 
        image = cv2.resize(image, size, interpolation = cv2.INTER_LINEAR) 
        return image
    
    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):
        datafiles = self.files[index]
        image = cv2.imread(datafiles["img"], cv2.IMREAD_COLOR)   
        label = sio.loadmat(datafiles['label'])['imgDepthFilled']
        ori_size = image.shape
        image = self.resize_image(image, (self.resize_w, self.resize_h))
        label = cv2.resize(label,(self.resize_w, self.resize_h))
         
        name = datafiles["name"]
        image = np.asarray(image, np.float32)
        image -= self.mean
#######crop
        image_cropped = np.zeros((self.crop_h, self.crop_w, 3), dtype=np.float32)
        label_cropped = np.zeros((self.crop_h, self.crop_w), dtype=np.float32)
        img_h, img_w = label.shape
        pad_h = max(img_h-self.crop_h , 0)
        pad_w = max(img_w-self.crop_w , 0)
     #   
        h_off = random.randint(0, pad_h)
        w_off = random.randint(0, pad_w) 

        h_off = random.randint(0, pad_h)
        w_off = random.randint(0, pad_w) 
        image_cropped = image[h_off:h_off+self.crop_h, w_off:w_off+self.crop_w]
        label_cropped = label[h_off:h_off+self.crop_h, w_off:w_off+self.crop_w]
        
        image_cropped = image_cropped.transpose((2, 0, 1))
        return image_cropped, label_cropped,  np.array(ori_size), name
     
 
class LIPDataTestSet(data.Dataset):
    def __init__(self, root, list_path, crop_size=(473, 473), mean=(128, 128, 128), img_size=[400], mirror=False):
        self.root = root 
        self.list_path = list_path
        self.crop_h, self.crop_w = crop_size
        self.mean = mean
        self.img_size = img_size
        self.mirror = mirror
         
        
        self.img_ids = [json.loads(i_id.rstrip()) for i_id in open(list_path)]
                
        self.files = []
         
        for item in self.img_ids:
           # image_path, label_path, label_rev_path, edge_path = item
            image_path = item['fpath_img']
            name = osp.splitext(osp.basename(image_path))[0]  
            img_file = osp.join(self.root, image_path)
            self.files.append({
                "img": img_file,
                "name": name
            })

        assert isinstance(img_size, list)
          
    def __len__(self):
        return len(self.files)
    
    def resize_image(self, image, size): 
        image = cv2.resize(image, size, interpolation = cv2.INTER_LINEAR) 
        return image
    
    def __getitem__(self, index):
        '''
        Will return a set of augmented images, the first half of the set are
        images whose long edge is resized according to self.img_size, and the
        other half are their mirrorrs.
        '''
        datafiles = self.files[index] 
        image = cv2.imread(datafiles["img"], cv2.IMREAD_COLOR)  
        ori_size = image.shape 
        #image = self.resize_image(image, (self.crop_h, self.crop_w))
         
        img_resized_list = []
        for this_long_size in self.img_size:
            this_scale = this_long_size / float(max(ori_size[0], ori_size[1]))  
            resized_img = self.resize_image(image, (int(this_scale*ori_size[0]), int(this_scale*ori_size[1])))
            resized_img = np.asarray(resized_img, np.float32)
            resized_img -= self.mean 
            resized_img = resized_img.transpose((2, 0, 1))
            img_resized_list.append(resized_img)

        if self.mirror==True:
            pass

        ori_img = np.asarray(image, np.float32)
        ori_img -= self.mean 
        ori_img = ori_img.transpose((2, 0, 1))
        return ori_img, img_resized_list, np.array(ori_size), datafiles["name"]
    

