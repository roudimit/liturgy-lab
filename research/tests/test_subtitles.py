from liturgy_lab.subtitles import timestamp,to_vtt

def test_rounding_and_absolute_timestamps():
    assert timestamp(3599.9998)=='01:00:00.000'
    assert '00:30:07.000 --> 00:30:10.000' in to_vtt([{'start':1807,'end':1810,'text':'<prayer>'}])
    assert '&lt;prayer&gt;' in to_vtt([{'start':1,'end':2,'text':'<prayer>'}])
