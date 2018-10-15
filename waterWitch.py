#! /sbin/env python3

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from datetime import timedelta

#                                _______     ______________     _______________
#                               |       |   |              |   |               |
#  _________     ___________    | Queue |==>| AudioConvert |==>| AutoVideoSink |===> ALSA
# |         |   |           |==>|_______|   |______________|   |_______________|
# | Filesrc |==>| DecodeBin |    _______     ______________     _______________
# |_________|   |___________|==>|       |   |              |   |               |
#                               | Queue |==>| VideoConvert |==>| AutoVideoSink |===> X11
#                               |_______|   |______________|   |_______________|

class Player(object):
    def __init__(self, filepath):

        Gst.init(None)
        self.mainloop = GLib.MainLoop()
        self.progress = GLib.timeout_add_seconds(interval=1, function=self.progress_callback)
        self.pipeline = Gst.Pipeline()

        self.src = Gst.ElementFactory.make('filesrc','src')
        self.src.set_property('location', filepath)

        self.vqueue = Gst.ElementFactory.make('queue', 'vqueue')
        self.aqueue = Gst.ElementFactory.make('queue', 'aqueue')

        self.decode = Gst.ElementFactory.make('decodebin', 'decode')
        self.decode.connect("pad-added", self.on_decoder_pad_added)

        self.videoconvert = Gst.ElementFactory.make('videoconvert', 'videoconvert')
        self.audioconvert = Gst.ElementFactory.make('audioconvert', 'audioconvert')

        self.muxer = Gst.ElementFactory.make('qtmux', 'muxer')

        self.sink = Gst.ElementFactory.make('filesink', 'sink')
        self.sink.set_property('sync', False)
        self.sink.set_property('location', 'ouput.mp4')

        self.vsink = Gst.ElementFactory.make('autovideosink', 'vsink')
        self.asink = Gst.ElementFactory.make('autoaudiosink', 'asink')

        self.pipeline.add(self.src)
        self.pipeline.add(self.vqueue)
        self.pipeline.add(self.aqueue)
        self.pipeline.add(self.decode)
        self.pipeline.add(self.videoconvert)
        self.pipeline.add(self.audioconvert)
        self.pipeline.add(self.vsink)
        self.pipeline.add(self.asink)

        self.src.link(self.decode)

        self.vqueue.link(self.videoconvert)
        self.videoconvert.link(self.vsink)

        self.aqueue.link(self.audioconvert)
        self.audioconvert.link(self.asink)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::error', self.on_error)
        self.bus.connect('message::state-changed', self.on_status_changed)
        self.bus.connect('message::eos', self.on_eos)
        self.bus.connect('message::info', self.on_info)
        self.bus.connect('message::progress', self.on_progress)
        self.bus.connect('message', self.on_message)
        self.bus.enable_sync_message_emission()

    def on_status_changed(self, bus, message):
        oldState, newState, pending = message.parse_state_changed()
        print('status_changed message -> from: {}, to {}, pending: {}'.format(oldState, newState, pending))
        print('from: {}'.format(message.src is self.pipeline))
        if message.src is self.pipeline and oldState == Gst.State.READY and newState == Gst.State.PAUSED:
            seekable = self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 10 * Gst.SECOND)
            print("Seek: " + str(seekable))
            self.pipeline.set_state(Gst.State.PLAYING)

    def on_eos(self, bus, message):
        print('eos message -> {}'.format(message))

    def on_info(self, bus, message):
        print('info message -> {}'.format(message))

    def on_error(self, bus, message):
        print('error message -> {}'.format(message.parse_error()))

    def on_progress(self, bus, message):
        print('progress message -> {}'.format(message))

    def on_message(self, bus, message):
        pass
        #print('received message: {}'.format(message.type))

    def on_decoder_pad_added(self, demuxer, pad):
        trackType = pad.get_current_caps()[0].get_name()
        if trackType.startswith('video'):
            pad.link(self.vqueue.get_static_pad("sink"))

        if trackType.startswith('audio'):
           pad.link(self.aqueue.get_static_pad("sink"))

    def progress_callback(self):
        self.progress = GLib.timeout_add_seconds(interval=1, function=self.progress_callback)
        success, position = self.pipeline.query_position(Gst.Format.TIME)
        print("Progress: {}".format(timedelta(microseconds=position / 1000)))
        if position > (13 * Gst.SECOND):
            self.stop()

    def run(self):

        self.pipeline.set_state(Gst.State.PAUSED)
        self.mainloop.run()

    def stop(self):
        print("Kill it with file")
        self.pipeline.set_state(Gst.State.NULL)
        self.mainloop.quit()

p = Player('big_buck_bunny_480p_stereo.avi')
#p = Player('tearsofsteel_4k.mov')
p.run()
print('Bye...')
