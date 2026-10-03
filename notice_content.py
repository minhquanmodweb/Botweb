"""Allowlisted rich-text notice HTML; no executable markup or remote fetching."""
import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

TAGS={'p','div','br','strong','b','em','i','u','ul','ol','li','blockquote','a','img','video','source','span','font','h2','h3'}
VOID={'br','img','source'}
DROP={'script','style','iframe','object','embed','svg','math','template'}
COLOR=re.compile(r'^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{1,20}|rgba?\([0-9., %]{1,40}\))$')

def safe_url(value,media=False):
 value=value.strip()
 if any(ord(c)<32 for c in value):return ''
 try:u=urlsplit(value)
 except ValueError:return ''
 if u.scheme.lower() in ('https','http') and u.netloc and not u.username and not u.password:return value
 if value.startswith('/api/notice-media/') and re.fullmatch(r'/api/notice-media/[a-f0-9]{32}\.(jpg|png|webp|gif|mp4|webm)',value):return value
 if not media and value.startswith('/') and not value.startswith('//'):return value
 return ''

class Cleaner(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.output=[];self.stack=[];self.drop=[]
 def handle_starttag(self,tag,attrs):
  if self.drop:
   if tag in DROP:self.drop.append(tag)
   return
  if tag in DROP:self.drop.append(tag);return
  if tag not in TAGS:return
  attrs=dict(attrs);values=[]
  if tag in ('a','img','video','source'):
   key='href' if tag=='a' else 'src';url=safe_url(attrs.get(key) or '',tag!='a')
   if url:values.append((key,url))
   if tag=='a':values.extend([('target','_blank'),('rel','noopener noreferrer')])
   if tag=='img':values.extend([('alt',(attrs.get('alt') or '')[:200]),('loading','lazy')])
   if tag=='video':
    values.extend([('controls',''),('preload','metadata'),('playsinline','')])
    poster=safe_url(attrs.get('poster') or '',True)
    if poster:values.append(('poster',poster))
  color=''
  for part in (attrs.get('style') or '').split(';'):
   key,_,value=part.partition(':')
   if key.strip().lower()=='color' and COLOR.fullmatch(value.strip()):color=value.strip()
  if tag=='font' and COLOR.fullmatch(attrs.get('color') or ''):color=attrs['color']
  if color:values.append(('style','color:'+color))
  self.output.append('<'+('span' if tag=='font' else tag)+''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in values)+'>')
  if tag not in VOID:self.stack.append(tag)
 def handle_endtag(self,tag):
  if self.drop:
   if tag==self.drop[-1]:self.drop.pop()
   return
  if tag in self.stack:
   while self.stack:
    current=self.stack.pop();self.output.append('</'+('span' if current=='font' else current)+'>')
    if current==tag:break
 def handle_data(self,data):
  if not self.drop:self.output.append(html.escape(data))
 def handle_startendtag(self,tag,attrs):
  self.handle_starttag(tag,attrs)
  if tag not in VOID:self.handle_endtag(tag)
 def finish(self):
  while self.stack:
   current=self.stack.pop();self.output.append('</'+('span' if current=='font' else current)+'>')
  return ''.join(self.output)

def clean_html(value):
 parser=Cleaner();parser.feed(value);return parser.finish()

def plain_html(value):
 return '<p>'+html.escape(value).replace('\n','<br>')+'</p>'
