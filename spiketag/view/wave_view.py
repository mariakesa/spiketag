import numpy as np
from vispy import scene, app
from .MyWaveVisual import MyWaveVisual
from .color_scheme import palette
from ..view import Picker, YSyncCamera
from vispy.util import keys


class Axis(scene.AxisWidget):
    """from scene.AxisWidget"""
    def set_x_transform(self, x_transform):
        self.glpos_to_time = x_transform

    def set_y_transform(self, y_transform):
        self.glpos_to_value = y_transform

    def glpos_to_time(self, gl_pos):
        '''
        get time from the x postion of x_axis
        Important: check the affine transformation in MyWaveVisual!
        '''
        xn = np.ceil((gl_pos / 0.95 + 1) * (self.npts - 1) / 2)
        t = (xn + self._start_index + self._time_slice * self._time_span) / self.fs
        return t


    def glpos_to_value(self, gl_pos):
        '''
        get value from the y postion of y_axis
        Important: check the affine transformation in MyWaveVisual!
        '''
        y = (gl_pos+1-1./self.nCh) / 0.95 * self.nCh
        y = y*self.yscale
        return y
    
    def _view_changed(self, event=None):
        """Linked view transform has changed; update ticks.
        """
        tr = self.node_transform(self._linked_view.scene)
        p1, p2 = tr.map(self._axis_ends())
        if self.orientation in ('left', 'right'):
            # yaxis
            self.axis.domain = (self.glpos_to_value(p1[1]), self.glpos_to_value(p2[1]))
            # self.axis.domain = (p1[1],p2[1])
        else:
            # xaxis
            self.axis.domain = (self.glpos_to_time(p1[0]), self.glpos_to_time(p2[0]))


class Cross(object):
    def __init__(self, cursor_color):

        self.cross_state = False
        self.cursor_color = cursor_color
        self._time_slice = 0
        self.x_axis = Axis(orientation='bottom', text_color=cursor_color, tick_color=cursor_color, axis_color=cursor_color)
        self.x_axis.stretch = (1, 0.1)
        self.y_axis = Axis(orientation='left', text_color=(1, 1, 1, 0), tick_color=cursor_color, axis_color=cursor_color)
        self.y_axis.stretch = (0, 1)
        self.y_axis_ref = Axis(orientation='left', text_color=(1, 1, 1, 0), tick_color=(1, 1, 1, 0), axis_color=(0, 1, 1))
        self.y_axis_ref.stretch = (0, 1)

    def set_params(self, nCh, npts, fs, time_slice, time_span, yscale=1):
        self.x_axis.unfreeze()
        self.x_axis.npts = npts
        self.x_axis.fs = fs
        self.x_axis._time_slice = 0
        self.x_axis._time_span = npts
        self.x_axis._start_index = 0
        self.x_axis.freeze()

        self.y_axis.unfreeze()
        self.y_axis.nCh = nCh
        self.y_axis.npts = npts
        self.y_axis.fs = fs
        self.y_axis._time_slice = 0
        self.y_axis._time_span = npts
        self.y_axis._start_index = 0
        self.y_axis.yscale = yscale
        self.y_axis.freeze()

        self.y_axis_ref.unfreeze()
        self.y_axis_ref.nCh = nCh
        self.y_axis_ref.npts = npts
        self.y_axis_ref.fs = fs
        self.y_axis_ref._time_slice = 0
        self.y_axis_ref._time_span = npts
        self.y_axis_ref.yscale = yscale
        self.y_axis_ref._start_index = 0
        self.y_axis_ref.freeze()

    def attach(self, parent):
        parent.add_widget(self.x_axis)
        parent.add_widget(self.y_axis)
        parent.add_widget(self.y_axis_ref)

    def enable_tick(self, axis=1):
        if axis==1:
            self.y_axis.axis._text.color = self.cursor_color
            # print self.y_axis.orientation

    def disable_tick(self, axis=1):
        if axis==1:
            self.y_axis.axis._text.color = (1, 1, 1, 0)      

    def link_view(self, view):
        self.x_axis.link_view(view)
        self.y_axis.link_view(view)
        self.y_axis_ref.link_view(view)
        self.y_axis_ref.visible = False
        self.parentview = view

    def moveto(self, pos):
        pos = pos - self.parentview.pos - self.parentview.margin
        self.x_axis.transform.translate = (0, pos[1])
        self.y_axis.transform.translate = (pos[0], 0)

    def flip_state(self):
        self.cross_state = not self.cross_state

    def ref_enable(self, pos):
        pos = pos - self.parentview.pos - self.parentview.margin
        self.y_axis_ref.transform.translate = (pos[0], 0)
        self.y_axis_ref.visible = True

    def ref_disable(self):
        self.y_axis_ref.visible = False

    @property
    def time_slice(self):
        return self._time_slice

    @time_slice.setter
    def time_slice(self, time_slice_no):
        self._time_slice = time_slice_no
        self.x_axis._time_slice = time_slice_no
        self.x_axis._view_changed()
        self.y_axis._time_slice = time_slice_no
        self.y_axis._view_changed()

    def view_changed(self):
        self.x_axis._view_changed()
        self.y_axis._view_changed()

    def start_index_changed(self, index):
        self.x_axis._start_index = index
        self.y_axis._start_index = index
        self.y_axis_ref._start_index = index


class wave_view(scene.SceneCanvas):

    '''
        Wave view can show trace with or without highlight spikes.

        Parameters
        ----------
        data : array-like
            the raw data of wave. If chNos is none, show 32 channel at most.
        fs : float
            the sample rate
        spks : array-like
            the pivotal postion of spikes, support two formats. Look examples for more details.
        chs: array-like
            the specific channels which want to show, it chs is none, show the first 32 channels (0-31). 

        Examples
        ----------
        Example1: show trace without spikes
            wview = wave_view(x[:64000, 0:32], fs=fs, ncols=1)
            wview.show()

        Example2: show trace with spikes, spikes is an array-like, suport two formats, i.e:
            
            format 1 which shape should be (2, n):
                _spks = array([[      24,       25,       90, ..., 20029531, 20029562, 20029607],
                              [       9,       16,       12, ...,       31,       25,       25]], dtype=int32)

            format 2 which shape shold be (n, ), and n should be even:
                _spks = array([24, 9, 25, 16, 90, 12, ..., 20029531, 31, 20029562, 25, 20029607, 25], dype=int32)

            wview = wave_view(x[:64000, 0:32], spks=_spks)
            wview.show()

        Example3: show trace with specific channels
            wview = wave_view(data=data, spks=spks, chs=[i for i in range(32) if i % 5 == 1])
            wview.show()
            
            chs = array([[ 68,  69,  74,  75],
                         [ 70,  71,  72,  73]])
            wview = wave_view(data=data, fs=fs, chs=chs)
            wview.show()
    '''

    def __init__(self, data=None, fs=25e3, spks=None, chs=None, color=None, pagesize=20000, ncols=1, gap_value=0.8*0.95, ls='-', time_slice=0):
        scene.SceneCanvas.__init__(self, keys=None)
        self.unfreeze()

        assert data is not None

        self.grid1 = self.central_widget.add_grid(spacing=0, bgcolor='gray',
                                                 border_color='k')
        self.view2 = self.grid1.add_view(row=0, col=1, col_span=36, margin=10, bgcolor=(0, 0, 0, 1),
                              border_color=(0, 1, 0))
        self.view2.camera = scene.cameras.PanZoomCamera()
        self.view2.camera.set_range()
        self.cursor_color = '#0FB6B6'
        self.cursor_text = scene.Text("", pos=(0, 0), italic=False, bold=True, anchor_x='left', anchor_y='center',
                                 color=self.cursor_color, font_size=14, parent=self.view2.scene)
        self.cursor_text_ref = scene.Text("", pos=(0, 0), italic=True, bold=False, anchor_x='left', anchor_y='center',
                                     color=(0, 1, 1, 1), font_size=14, parent=self.view2.scene)

        self.palette = palette
        self._gap_value = gap_value
        self.fs = fs
        
        wav_visual = scene.visuals.create_visual_node(MyWaveVisual)
        self.waves1 = wav_visual(ls=ls, parent=self.view2.scene, 
                                 color=color,
                                 gap=self._gap_value)

        self.grid2 = self.view2.add_grid(spacing=0, bgcolor=(0, 0, 0, 0), border_color='k')
        self.cross = Cross(cursor_color=self.cursor_color)
        self.timer_cursor = app.Timer(connect=self.update_cursor, interval=0.01, start=False)

        self.view1 = self.grid1.add_view(row=0, col=0, col_span=1, margin=10, bgcolor=(0, 0, 0, 1),
                          border_color=(1, 0, 0))
        self.view1.camera = scene.cameras.PanZoomCamera()
        self.view1.camera.set_range()

        self._start_index = 0
        self.flag = 0
        self._pagesize = pagesize
        self.location = ''
        y_sync_cam = YSyncCamera()
        self.view1.camera.link(y_sync_cam)
        self.view2.camera.link(y_sync_cam)

        self.ch_no_text = scene.Text('', pos=(0,0),italic=False, bold=True,
                         color=self.cursor_color, font_size=12, parent=self.view1.scene) 
        
        self.data = data
        if chs is not None:
            chs = np.array(chs)
            if chs.ndim!=1:
                chs = chs.ravel()
            self.data = self.data[:, chs]
            chs_labels = chs
        elif self.data.shape[1] <= 32:
            chs_labels = np.arange(self.data.shape[1])
        else:
            chs_labels = np.arange(32)
        self._chs = list(zip(chs_labels, np.arange(len(chs_labels))))
        self._chs_idx = sorted([j for _, j in self._chs], reverse=True)
        self.spikes = self._spkarray2dist(spks) 
        self._render(self.data[0:self.pagesize, self._chs_idx])
        self.attach_texts()
        self.highlight_ch()
        self.set_range()
        self.cross.attach(self.grid2)
        self.cross.link_view(self.view2)

        self._current_time = 0.0
        self._sliding_time = 1.0
        
        # for picker
        self.key_option = 0
        self._picker = Picker(self.scene, self.view2.camera.transform)
        self.picked_data = []
    
    def _render(self, data):
        '''
          For now,wave_visual is the best place  where store the view information,
          and wave_view should get from it, otherwise,there are two copy of information,
          it is redundancy
        '''
        self.waves1.set_data(data)

        ####### get basic info from wave visual
        self.npts = self.waves1.npts
        self.nCh = self.waves1.nCh
        scale = self.waves1._scale

        ####### update cross #########
        self.cross.set_params(self.nCh, self.npts, self.fs, 0, 0, scale)

        ####### trigger timer ######
        self.timer_cursor.start()

    def _spkarray2dist(self, spks):
        if spks is None:
            return None

        dist = {}
        chs = dict(self._chs)

        # if format 1, convert to format 2
        if len(spks.shape) == 1:
            spks = spks.reshape(-1, 2).T

        for i in np.unique(spks[1]):
            if i in chs.keys():
                dist[chs[i]] = spks[0][spks[1] == i]

        return dist


    def convert_2_highlight_ch(self, chs):
        highlight_chs = np.array(self._chs_idx)[chs]
        return highlight_chs

    def highlight(self, chs, timelist, colorlist=None, mask_others=False):
        highlight_chs = self.convert_2_highlight_ch(chs)
        self.waves1.highlight_ch(highlight_chs, highlight_color=(1,1,1,1), mask_others=mask_others)
        self.waves1.highlight(highlight_chs, timelist, colorlist) 

    def highlight_ch(self):
        
        if getattr(self, 'spikes', None) is None or self.spikes is None:
            return

        for idx, val in enumerate(self._chs_idx):
            t = self.spikes.get(val, None)
            if t is not None:
                times = np.take(t, np.where((t >= self._start_index) & (t < self._start_index + self.pagesize)))[0] - self._start_index
                #  times = np.intersect1d(np.arange(self._start_index,self._start_index + self.pagesize),self.spks[0][self.spks[1] == val]) -  self._start_index
                if times.size > 0:
                    spks = np.column_stack((times, np.full(times.shape,idx, dtype=np.int64)))
                    self.waves1.highlight_spikes(spks)

    @property
    def gap_value(self):
        return self._gap_value

    @gap_value.setter
    def gap_value(self, value):
        if value >= 1:
            value == 1
        elif value <= 0:
            value = 0
        self._gap_value = value
        self.waves1.set_gap(self._gap_value)
        self.attach_texts()
        self.set_range()

        if value == 0:
            self.cross.enable_tick(axis=1)
        else:
            self.cross.disable_tick(axis=1)

    def set_range(self):
        gap = self.gap_value
        N = self.nCh
        bottom = -1 + 1./N - gap/N
        top    = bottom + gap*2
        self.view2.camera.set_range(x=(-1,1), y=(bottom, top))
        self.view2.camera.set_default_state()
        self.view2.camera.reset()


    def attach(self, gui):
        self.unfreeze()
        gui.add_view(self)

    def slideto(self, to):
        if to < self.data.shape[0]:
            self._start_index = int(to) - self.pagesize / 2
            if self._start_index < 0:
                self._start_index = 0
            self._render(self.data[int(self._start_index):int(self._start_index + self.pagesize), self._chs_idx])
            self.highlight_ch()
            self.cross.start_index_changed(self._start_index)
            self.cross.view_changed()

    def slide(self, offset):
        tmp = self._start_index + int(offset) * 10

        if tmp  >= 0 and tmp + self.pagesize < self.data.shape[0]:
            self._start_index = tmp
            self._render(self.data[int(self._start_index):int(self._start_index + self.pagesize), self._chs_idx])
            self.highlight_ch()
            self.cross.start_index_changed(self._start_index)
            self.cross.view_changed()
        elif tmp < 0:
            self._start_index = 0
    
    #  def select_ch(self, chs):
        #  self._selectchs = chs
        #  self.nCh = len(self.selectchs)
        #  self._render(self.data[self._start_index:self._start_index + self.pagesize, self.selectchs])
        #  self.highlight_ch()
        #  self.attach_texts()
        #  self.cross.start_index_changed(self._start_index)
        #  self.cross.view_changed()

        #  self.set_range()


    #  def select_group(self, groups):
        #  chs = np.array([],dtype='int32')
        #  for g in groups:
            #  chs = np.hstack((chs,self.spktag.probe.get_chs(g)))
        #  self._selectchs = np.unique(chs)
        #  self.nCh = len(self.selectchs)
        #  self._render(self.data[self._start_index:self._start_index + self.pagesize, self.selectchs])
        #  self.highlight_ch()
        #  self.attach_texts()
        #  self.cross.start_index_changed(self._start_index)
        #  self.cross.view_changed()

        #  self.set_range()

    def attach_texts(self):
        
        y = -1 + 2 * (np.arange(len(list(self._chs))) * self.gap_value + 0.5) / len(list(self._chs))
        poses = np.column_stack((np.zeros(len(list(self._chs))),y))
        texts = [ str(i) for i,_ in reversed(self._chs)] 
        
        self.ch_no_text.text = texts
        self.ch_no_text.pos = poses


    def update_cursor(self, ev):
        pos = (self.cross.y_axis.pos[0], 0)
        gl_pos = self.view2.camera.transform.imap(pos)[0]
        t = self.cross.y_axis.glpos_to_time(gl_pos)
        n = np.ceil(t*self.cross.y_axis.fs)
        self.cursor_text.text = "   t0=%.6f sec, n=%d point" % (t,n)
        offset_x = self.view2.camera.transform.imap(self.cross.y_axis.pos)[0]
        _pos = self.view2.pos[1] + self.view2.size[1]*0.99 # bottom
        offset_y = self.view2.camera.transform.imap((0,_pos))[1]
        self.cursor_text.pos = (offset_x, offset_y)

        if self.cross.y_axis_ref.visible is True:
            # 1. cursor_text
            self.cursor_text_ref.visible = True
            pos_ref = (self.cross.y_axis_ref.pos[0], 0)
            gl_pos = self.view2.camera.transform.imap(pos_ref)[0]
            t_ref = self.cross.y_axis_ref.glpos_to_time(gl_pos)
            # calculate the time difference between t_ref and t
            delta_t = (t_ref - t)*1000
            self.cursor_text_ref.text = "   t1-t0=%.2f ms" % delta_t
            offset_x = self.view2.camera.transform.imap(self.cross.y_axis_ref.pos)[0]
            offset_y = self.view2.camera.transform.imap(self.cross.x_axis.pos)[1]
            self.cursor_text_ref.pos = (offset_x, offset_y)

            # 2. cursor_rect
            # self.cursor_rect.visible = True
            # y_axis_pos = (self.cross.y_axis.pos[0]+self.view2.margin,0)
            # start_x = self.view2.camera.transform.imap(y_axis_pos)[0]
            # self.cursor_rect.center = (start_x+self.cursor_rect._width/2.+self.cursor_rect._border_width ,0, 0)
            # y_axis_ref_pos = (self.cross.y_axis_ref.pos[0]+self.view2.margin,0)
            # end_x   = self.view2.camera.transform.imap(y_axis_ref_pos)[0]
            # width = end_x - start_x
            # if width <= 0:
                # width = 1e-15
            # self.cursor_rect.width = width
            # height = self.view2.camera.transform.imap((0,-self.view2.size[1]))[1]
            # self.cursor_rect.height = height*2
        else:
            self.cursor_text_ref.visible = False
            # self.cursor_rect.visible = False

    def on_key_press(self, event):
        # if event.key.name == 'PageDown':
        #     print 'next page'

        # print event.key.name
        
        if keys.CONTROL in event.modifiers:
            self.view2.events.mouse_wheel.disconnect(self.view2.camera
                    .viewbox_mouse_event)

        if event.text == 'r':
            self.view2.camera.reset()
        elif event.text == 'c':
            self.cross.flip_state()
        elif event.text.isdigit():
            self.location += event.text
        elif event.text == 'g':
            if self.location.isdigit():
                second = int(self.location)
                self.slideto(second * self.fs)
                self._current_time = second
            self.location = ''
        elif event.text == 'h' or getattr(event.key, 'name', None) == 'Left':
            self._current_time = self._current_time - self._sliding_time
            self.slideto(self._current_time * self.fs)
        elif event.text == 'l' or getattr(event.key, 'name', None) == 'Right':
            self._current_time = self._current_time + self._sliding_time
            self.slideto(self._current_time * self.fs)
        elif event.text == '=':
            location = self._start_index + self.pagesize / 2
            self.pagesize += int(self.pagesize * 0.1)
            self.slideto(location)
        elif event.text == '-':
            location = self._start_index + self.pagesize / 2
            self.pagesize -= int(self.pagesize * 0.1)
            self.slideto(location)
        else:
            self.key_option = event.key.name
            # print event.text
     
    def on_key_release(self, e):
        if self.key_option == "Escape":
            self._picker.reset()
            self.picked_data = []
        self.key_option = 0   


    @property
    def pagesize(self):
        return self._pagesize

    @pagesize.setter
    def pagesize(self, val):
        if val <= 1000:
            self._pagesize = 1000
        elif val >= 500000:
            self._pagesize = 500000
        else:
           self._pagesize = val

    def on_mouse_move(self, event):
        modifiers = event.modifiers
        if 1 in event.buttons and modifiers is not ():
            p1 = event.press_event.pos
            p2 = event.last_event.pos
            if modifiers[0].name == 'Shift':
                self.cross.ref_enable(p2)
            if modifiers[0].name == 'Control':
                if self.key_option != 'W':
                    # print self.key_option
                    self.slide(event.pos[0]-self.last_x)
                if self.key_option == 'W':
                    # print self.key_option
                    self._picker.cast_net(event.pos,ptype='rectangle')


        elif self.cross.cross_state:
            if event.press_event is None:
                self.cross.moveto(event.pos)
                self.cross.ref_disable()

    def on_mouse_release(self, e):
        modifiers = e.modifiers
        if keys.CONTROL in  e.modifiers and e.is_dragging:
            mask = self._picker.pick(self.waves1.get_gl_pos(), auto_disappear=False)
            shift_mask = [i-8 for i in mask]
            self.picked_data = self.waves1.data[shift_mask]
            # print len(mask)
            # print mask
 
    def on_mouse_wheel(self, event):
        modifiers = event.modifiers
        if modifiers is not ():
            if modifiers[0].name=='Control':
                self.gap_value = self.gap_value + 0.05*event.delta[1]


    def on_mouse_press(self,e):
        modifiers = e.modifiers
        if modifiers is not ():
            if modifiers[0].name == 'Control':
                if self.key_option != 'W':
                    # print self.key_option
                    self.last_x = e.pos[0]
                if self.key_option == 'W':
                    # print self.key_option
                    self._picker.origin_point(e.pos)


# if __name__ == '__main__':
#     from phy.gui import GUI, create_app, run_app
#     create_app()
#     gui = GUI(position=(0, 0), size=(600, 400), name='GUI')
#     ##############################################
#     ### Test scatter_view
#     # from sklearn.preprocessing import normalize
#     # n = 1000000
#     # fet = np.random.randn(n,3)
#     # fet = normalize(fet,axis=1)
#     # print fet.shape
#     # clu = np.random.randint(3,size=(n,1))
#     # scatter_view = scatter_3d_view()
#     # scatter_view.attach(gui)
#     # scatter_view.set_data(fet, clu)
#     #############################################################################################
#     ### Set Parameters ###
#     filename  = '/tmp_data/pcie.bin'
#     nCh       = 32
#     fs        = 25000
#     numbyte   = 4
#     time_span = 1 # 1 seconds
#     global time_slice
#     time_slice = 0
#     span = time_span * fs
#     highlight = True
#     #############################################################################################
#     from Binload import Binload
#     ### Load data ###
#     lf = Binload(nCh=nCh, fs=fs)
#     lf.load(filename,'i'+str(numbyte), seekpos=0)
#     t, data = lf.tonumpyarray()
#     data = data/float(2**14)

#     ### wave_view ###
#     wview = wave_view(data[time_slice*span:(time_slice+1)*span,:], fs=25000)
#     wview.gap_value = 0.5*0.95
#     wview.attach(gui)

#     ############################################################################################
#     ### Add actions ###

#     from phy.gui import Actions
#     actions = Actions(gui)

#     @actions.add(shortcut=',')
#     def page_up():
#         global time_slice
#         time_slice -= 1
#         if time_slice >= 0:
#             wview.set_data(data[time_slice*span:(time_slice+1)*span,:], time_slice)
#         else:
#             time_slice = 0

#     @actions.add(shortcut='.')
#     def page_down():
#         global time_slice
#         time_slice += 1
#         wview.set_data(data[time_slice*span:(time_slice+1)*span,:], time_slice)

#     ##############################################################################################
#     gui.show()
#     run_app()
