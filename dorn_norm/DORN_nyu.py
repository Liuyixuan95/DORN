# -*- coding: utf-8 -*-
# @Time    : 2018/11/22 12:33
# @Author  : Wang Xin
# @Email   : wangxin_buaa@163.com
import os

import torch
import torch.nn as nn
import torchvision.models
import collections
import math


def weights_init(m):
    # Initialize filters with Gaussian random weights
    if isinstance(m, nn.Conv2d):
        n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
        m.weight.data.normal_(0, math.sqrt(2. / n))
        if m.bias is not None:
            m.bias.data.zero_()
    elif isinstance(m, nn.ConvTranspose2d):
        n = m.kernel_size[0] * m.kernel_size[1] * m.in_channels
        m.weight.data.normal_(0, math.sqrt(2. / n))
        if m.bias is not None:
            m.bias.data.zero_()
    elif isinstance(m, nn.BatchNorm2d):
        m.weight.data.fill_(1)
        m.bias.data.zero_()


class FullImageEncoder(nn.Module):
    def __init__(self):
        super(FullImageEncoder, self).__init__()
        self.global_pooling = nn.AvgPool2d(8, stride=8, padding=(4, 2))  # KITTI 16 16
        self.dropout = nn.Dropout2d(p=0.5)
        self.global_fc = nn.Linear(2048 * 6 * 5, 512)
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(512, 512, 1)  # 1x1 卷积
        self.upsample = nn.UpsamplingBilinear2d(size=(33, 45))  # KITTI 49X65 NYU 33X45

    def forward(self, x):
        x1 = self.global_pooling(x)
        # print('# x1 size:', x1.size())
        x2 = self.dropout(x1)
        x3 = x2.view(-1, 2048 * 6 * 5)
        x4 = self.relu(self.global_fc(x3))
        # print('# x4 size:', x4.size())
        x4 = x4.view(-1, 512, 1, 1)
        # print('# x4 size:', x4.size())
        x5 = self.conv1(x4)
        out = self.upsample(x5)
        return out


class SceneUnderstandingModule(nn.Module):
    def __init__(self):
        super(SceneUnderstandingModule, self).__init__()
        self.encoder = FullImageEncoder()
        self.aspp1 = nn.Sequential(
            nn.Conv2d(2048, 512, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 1),
            nn.ReLU(inplace=True)
        )
        self.aspp2 = nn.Sequential(
            nn.Conv2d(2048, 512, 3, padding=6, dilation=6),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 1),
            nn.ReLU(inplace=True)
        )
        self.aspp3 = nn.Sequential(
            nn.Conv2d(2048, 512, 3, padding=12, dilation=12),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 1),
            nn.ReLU(inplace=True)
        )
        self.aspp4 = nn.Sequential(
            nn.Conv2d(2048, 512, 3, padding=18, dilation=18),
            nn.ReLU(inplace=True),
            nn.Conv2d(512, 512, 1),
            nn.ReLU(inplace=True)
        )
        self.concat_process = nn.Sequential(
            nn.Dropout2d(p=0.5),
            nn.Conv2d(512 * 5, 2048, 1),
            nn.ReLU(inplace=True),
            nn.Dropout2d(p=0.5),
            nn.Conv2d(2048, 160, 1),  # KITTI 142 NYU 136 In paper, K = 80 is best, so use 160 is good!
           # nn.Conv2d(2048, 1, 1),  # KITTI 142 NYU 136 In paper, K = 80 is best, so use 160 is good!
            # nn.UpsamplingBilinear2d(scale_factor=8)
            nn.UpsamplingBilinear2d(size=(257, 353))
        )

    def forward(self, x):
        x1 = self.encoder(x)

        x2 = self.aspp1(x)
        x3 = self.aspp2(x)
        x4 = self.aspp3(x)
        x5 = self.aspp4(x)

        x6 = torch.cat((x1, x2, x3, x4, x5), dim=1)
        # print('cat x6 size:', x6.size())
        out = self.concat_process(x6)
        return out


class OrdinalRegressionLayer(nn.Module):
    def __init__(self):
        super(OrdinalRegressionLayer, self).__init__()

    def forward(self, x):
        """
        :param x: N X H X W X C, N is batch_size, C is channels of features
        :return: ord_labels is ordinal outputs for each spatial locations , size is N x H X W X C (C = 2K, K is interval of SID)
                 decode_label is the ordinal labels for each position of Image I
        """
        N, C, H, W = x.size()
        if torch.cuda.is_available():
            decode_label = torch.zeros((N, 1, H, W), dtype=torch.float32).cuda()
            ord_labels = torch.zeros((N, C // 2, H, W), dtype=torch.float32).cuda()
        else:
            decode_label = torch.zeros((N, 1, H, W), dtype=torch.float32)
            ord_labels = torch.zeros((N, C // 2, H, W), dtype=torch.float32)
        # print('#1 decode size:', decode_label.size())
        ord_num = C // 2
        """
        replace iter with matrix operation
        fast speed methods
        """
        A = x[:, ::2, :, :].clone()
        B = x[:, 1::2, :, :].clone()
        # print('A size:', A.size())
        # print('B size:', B.size())

        A = A.view(N, 1, ord_num * H * W)
        B = B.view(N, 1, ord_num * H * W)

        C = torch.cat((A, B), dim=1)

        ord_c = nn.functional.softmax(C, dim=1)

        # print('C size:', C.size())
        # print('ord_c size:', ord_c.size())

        ord_c1 = ord_c[:, 1, :].clone()
        ord_c1 = ord_c1.view(-1, ord_num, H, W)
        decode_c = torch.sum(ord_c1>=0.5, dim=1).view(-1, 1, H, W).float()
        # print('ord_c1 size:', ord_c1.size())

       # print('decode_label size:', decode_label.size())
       # print('decode_label size:', decode_label)
        return decode_c, ord_c1


class ResNet(nn.Module):
    def __init__(self, in_channels=3, pretrained=True):
        super(ResNet, self).__init__()
        pretrained_model = torchvision.models.__dict__['resnet{}'.format(101)](pretrained=pretrained)
       # print(type(pretrained_model))
      #  pretrained_model.load_state_dict(torch.load('./dataset/resnet101-5d3b4d8f.pth'))
       # print(type(pretrained_model))

        self.channel = in_channels

        self.conv1 = nn.Sequential(collections.OrderedDict([
            ('conv1_1', nn.Conv2d(self.channel, 64, kernel_size=3, stride=2, padding=1, bias=False)),
            ('bn1_1', nn.BatchNorm2d(64)),
            ('relu1_1', nn.ReLU(inplace=True)),
            ('conv1_2', nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1, bias=False)),
            ('bn_2', nn.BatchNorm2d(64)),
            ('relu1_2', nn.ReLU(inplace=True)),
            ('conv1_3', nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1, bias=False)),
            ('bn1_3', nn.BatchNorm2d(128)),
            ('relu1_3', nn.ReLU(inplace=True))
        ]))

        self.bn1 = nn.BatchNorm2d(128)

        # print(pretrained_model._modules['layer1'][0].conv1)

        self.relu = pretrained_model._modules['relu']
        self.maxpool = pretrained_model._modules['maxpool']
        self.layer1 = pretrained_model._modules['layer1']
        self.layer1[0].conv1 = nn.Conv2d(128, 64, kernel_size=(1, 1), stride=(1, 1), bias=False)
        self.layer1[0].downsample[0] = nn.Conv2d(128, 256, kernel_size=(1, 1), stride=(1, 1), bias=False)

        self.layer2 = pretrained_model._modules['layer2']

        self.layer3 = pretrained_model._modules['layer3']
        self.layer3[0].conv2 = nn.Conv2d(256, 256, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1), bias=False)
        self.layer3[0].downsample[0] = nn.Conv2d(512, 1024, kernel_size=(1, 1), stride=(1, 1), bias=False)

        self.layer4 = pretrained_model._modules['layer4']
        self.layer4[0].conv2 = nn.Conv2d(512, 512, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1), bias=False)
        self.layer4[0].downsample[0] = nn.Conv2d(1024, 2048, kernel_size=(1, 1), stride=(1, 1), bias=False)

        # clear memory
        del pretrained_model

        weights_init(self.conv1)
        weights_init(self.bn1)
        weights_init(self.layer1[0].conv1)
        weights_init(self.layer1[0].downsample[0])
        weights_init(self.layer3[0].conv2)
        weights_init(self.layer3[0].downsample[0])
        weights_init(self.layer4[0].conv2)
        weights_init(self.layer4[0].downsample[0])

    def forward(self, x):
        # print(pretrained_model._modules)

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)

        # print('conv1:', x.size())

        x = self.maxpool(x)

        # print('pool:', x.size())

        x1 = self.layer1(x)
        # print('layer1 size:', x1.size())
        x2 = self.layer2(x1)
        # print('layer2 size:', x2.size())
        x3 = self.layer3(x2)
        # print('layer3 size:', x3.size())
        x4 = self.layer4(x3)
        # print('layer4 size:', x4.size())
        return x4


class DORN(nn.Module):
    def __init__(self, output_size=(257, 353), channel=3):
        super(DORN, self).__init__()

        self.output_size = output_size
        self.channel = channel
        self.feature_extractor = ResNet(in_channels=channel, pretrained=True)
        self.aspp_module = SceneUnderstandingModule()
        self.orl = OrdinalRegressionLayer()

    def forward(self, x):
        x1 = self.feature_extractor(x)
        # print(x1.size())
        x2 = self.aspp_module(x1)
       # return x2
        # print('DORN x2 size:', x2.size())
        depth_labels, ord_labels = self.orl(x2)
        return depth_labels, ord_labels


# os.environ["CUDA_VISIBLE_DEVICES"] = "1"  # 默认使用GPU 0

if __name__ == "__main__":
    model = DORN()
    model = model.cuda()
    model.eval()
    image = torch.randn(1, 3, 257, 353)
    image = image.cuda()
    with torch.no_grad():
        out0, out1 = model(image)
    print('out0 size:', out0.size())
    print('out1 size:', out1.size())
