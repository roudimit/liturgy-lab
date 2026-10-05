"""Export actual raw ASR timestamps; no matched-text substitution."""
import html

def timestamp(seconds):
    milliseconds=round(max(0,seconds)*1000)
    hours,milliseconds=divmod(milliseconds,3600000)
    minutes,milliseconds=divmod(milliseconds,60000)
    seconds,milliseconds=divmod(milliseconds,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}'

def to_vtt(segments):
    lines=['WEBVTT','']
    for i,s in enumerate(segments):
        if s['end']<=s['start']:
            continue
        lines += [str(i+1),f"{timestamp(s['start'])} --> {timestamp(s['end'])}",html.escape(s['text']).replace('\n',' '),'']
    return '\n'.join(lines)
