#!/usr/bin/env python
# -*- coding: utf-8 -*-
import multiprocessing
import wx
from proxy_server import (
    ServerManager,
    q,
    IP,
    PORT
)
import time
from wx.adv import TaskBarIcon
import images
import requests
from wx.lib.agw import infobar
import getpass
import threading
from wx.lib.delayedresult import startWorker


class TaskBarIcon(TaskBarIcon):
    ID = wx.NewId()

    def __init__(self, frame):
        wx.adv.TaskBarIcon.__init__(self)
        self.frame = frame
        self.SetIcon(wx.Icon(images.icon.GetIcon()))

    # override
    def CreatePopupMenu(self):
        self.frame.Raise()


class MyWin(wx.Frame):

    def __init__(self, parent, title):
        super(MyWin, self).__init__(parent, title=title, size=(800, 600))
        self.SetMinSize((800, 600))
        self.msg = ''
        self.init_ui()
        self.Centre()
        self.Show()
        self.SetIcon(images.icon.GetIcon())
        self.job_id = 1

    def init_ui(self):
        self.task_bar_icon = TaskBarIcon(self)
        self.Bind(wx.adv.EVT_TASKBAR_CLICK, self.on_task_bar_left_dclick)
        panel = wx.Panel(self)
        sizer = wx.GridBagSizer(0, 0)
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.PointSize = 16
        self.SetFont(font)

        download_url = wx.StaticText(panel, label="游戏文件下载地址:")
        download_url.SetFont(font)
        sizer.Add(download_url, pos=(0, 0), flag=wx.ALL, border=10)

        all_download_url = wx.StaticText(panel, label="所有需要下载的文件:")
        all_download_url.SetFont(font)
        sizer.Add(all_download_url, pos=(1, 0), flag=wx.ALL, border=10)

        self.tc1 = wx.TextCtrl(panel, size=(200, 100), style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.tc1, pos=(0, 1), flag=wx.EXPAND | wx.ALL, border=5)

        self.tc2 = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self.tc2, pos=(1, 1), flag=wx.EXPAND | wx.ALL, border=5)

        sizer.AddGrowableCol(1)
        sizer.AddGrowableRow(1)

        self.btn1 = wx.Button(panel, -1, '\r获取所有游戏文件下载地址\r')
        self.btn1.SetFont(font)
        self.btn1.Bind(wx.EVT_BUTTON, self.on_clicked)
        sizer.Add(self.btn1, pos=(0, 2), flag=wx.ALL | wx.ALIGN_CENTER, border=5)
        panel.SetSizerAndFit(sizer)

        hint_msg = wx.StaticText(panel, size=(200, 100), label="提示:\r通过第三方下载工具将文件下载至\r/Users/{}/Downloads".format(getpass.getuser()))
        sizer.Add(hint_msg, pos=(1, 2), flag=wx.ALL, border=5)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(500)

        self.Bind(wx.EVT_CLOSE, self.on_exit)

        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetFieldsCount(2)
        self.SetStatusWidths([-1, 330])
        self.statusbar.SetStatusText('Starting proxy server on {} port {}'.format(IP, PORT), 0)

    def check_download_pkg(self):
        url = self.msg
        urls = '{}'.format(url)
        _url = url.split('.pkg')[0]
        no = int(_url[-2:])
        for i in xrange(1, 10):
            next_url = '{}{:0>2d}.pkg'.format(_url[:-2], no + i)
            resp = requests.head(next_url, timeout=10)
            if resp.status_code == 200:
                urls += '\r\n{}'.format(next_url)
            else:
                break
        return urls

    def on_clicked(self, event):
        if self.msg != '':
            self.btn1.Enable(False)
            self.tc2.SetValue('查询中请稍后。。。。。。_(:з」∠)_')
            startWorker(self._resultConsumer, self._resultProducer, jobID=self.job_id)

    def _resultConsumer(self, delayedResult):
        job_id = delayedResult.getJobID()
        assert job_id == self.job_id
        try:
            result = delayedResult.get()
        except Exception as e:
            return
        self.tc2.SetValue(result)
        self.btn1.Enable(True)

    def _resultProducer(self):
        urls = self.check_download_pkg()
        return urls

    def on_timer(self, event):
        try:
            msg = q.get(block=False)
            if type(msg) is str:
                self.msg = msg
                self.tc1.SetValue(msg)
            elif msg == 48:
                self.statusbar.SetStatusText('Error: Address already in use: ({}, {}).'.format(IP, PORT))
                dlg = wx.MessageDialog(self, 'Address already in use: ({}, {}).'.format(IP, PORT), 'Error:', wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
            elif type(msg) is list:
                if msg[0] == 200:
                    self.statusbar.SetStatusText(msg[1], 1)
        except Exception as e:
            pass

    def on_exit(self, event):
        p.terminate()
        time.sleep(0.1)
        wx.Exit()

    def on_task_bar_left_dclick(self, event):
        self.frame.Show(True)
        self.frame.Raise()

if __name__ == '__main__':
    p_server = ServerManager()
    app = wx.App()
    my_win = MyWin(None, 'PS4 download helper (alpha)')
    p = multiprocessing.Process(target=p_server.start)
    p.start()
    app.MainLoop()
