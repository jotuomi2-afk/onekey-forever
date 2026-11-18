"""Build OneKeyDruid/QuestData.lua from a Polestar_QuestDB folder.

Usage: python3 tools/extract_questdb.py <path/to/Polestar_QuestDB> OneKeyDruid/QuestData.lua

The source data is pfQuest's (MIT, Copyright (c) 2017-2021 Eric Mauser (Shagu)),
as packaged by Polestar. Keeps quests up to level ~48 for both factions; the
addon filters by race, class and faction at run time.
"""
import re,sys,os
D=os.path.join(sys.argv[1],'')
def rows(fn): return re.findall(r"^(-?\d+)\t'(.*)$",open(D+fn,encoding='utf-8').read(),re.M)
def lst(s):
    if not s: return []
    return [x for x in s.lstrip('{').split(',') if x]
def objs(s):
    v=lst(s); out=[];i=0
    while i<len(v):
        t=v[i]
        if t in('1','2') and i+2<len(v): out.append((t,v[i+1],v[i+2])); i+=3
        elif t in('1','2'): out.append((t,v[i+1] if i+1<len(v) else '','1')); i+=3
        else: out.append((t,v[i+1] if i+1<len(v) else '')); i+=2
    return out
Q={}
for qid,r in rows('Quests.lua'):
    f=r.split(';')+['']*20
    title,lvl,minl,races,classes,fac=f[0],f[1],f[2],f[3],f[4],f[5]
    if fac not in('1','2',''): continue
    if f[15] or f[14]: continue  # holiday, skill
    try: L=int(lvl or 0); M=int(minl or 0)
    except: continue
    if M>45 or L<=0 or L>48: continue
    Q[qid]=dict(r=races or '',c=classes or '',f=fac,t=title,l=L,m=M,s=lst(f[6]),e=lst(f[7]),p=lst(f[9]),pa=lst(f[16]),x=lst(f[10]),o=objs(f[11]),z=f[12])
need_n=set();need_o=set();need_i=set()
for q in Q.values():
    for s in q['s']+q['e']:
        (need_o if s.startswith('-') else need_n).add(s.lstrip('-'))
    for o in q['o']:
        if o[0]=='1': need_n.add(o[1])
        elif o[0]=='2': need_i.add(o[1])
        elif o[0]=='3': need_o.add(o[1])
I={}
for iid,r in rows('Items.lua'):
    if iid not in need_i: continue
    f=r.split(';'); name=f[0]; n=int(f[1] or 0); src=[]
    for k in range(n):
        src.append((f[2+2*k],float(f[3+2*k] or 0)))
    src.sort(key=lambda x:-x[1]); src=src[:3]
    for s,_ in src: need_n.add(s)
    I[iid]=(name,[s for s,_ in src])
def place(fields):
    # name;map;frame;count;x;y;r;... (first map only, first 3 clusters)
    name=fields[0]
    if len(fields)<4: return name,None
    m=fields[1]; c=int(fields[3] or 0); pts=[]
    for k in range(min(c,3)):
        b=4+3*k
        pts.append((fields[b],fields[b+1]))
    return name,(m,pts)
N={}
for nid,r in rows('Npcs.lua'):
    if nid in need_n: N[nid]=place(r.split(';'))
O={}
for oid,r in rows('Objects.lua'):
    if oid in need_o: O[oid]=place(r.split(';'))
def esc(s):
    import urllib.parse; s=urllib.parse.unquote(s)
    return s.replace('\\','\\\\').replace('"','\\"')
def pl(p):
    name,loc=p
    if not loc: return esc(name)
    return esc(name)+'|'+loc[0]+'|'+','.join(x+','+y for x,y in loc[1])
out=['-- OneKeyDruid/QuestData.lua: quests up to level ~45, both factions.',
'-- Extracted from the Polestar quest database (data from pfQuest, MIT, Copyright (c) 2017-2021 Eric Mauser (Shagu)).',
'-- quest: "title|level|minLevel|starters|enders|pre(one of)|preAll|excl|objectives|zone|raceMask|classMask|faction(1 A, 2 H)"',
'--   starters/enders: npc ids, "o" before an object id; objectives: k<npc>x<n> kill, i<item>x<n> item, o<object>, a<area>',
'-- npc/object: "name|uiMapID|x,y,x,y..."; item: "name|npc,npc,npc"',
'local _, ns = ...','ns.QDB = { q = {', ]
for qid in sorted(Q,key=int):
    q=Q[qid]
    def ids(v): return ','.join(('o'+x[1:]) if x.startswith('-') else x for x in v)
    ob=[]
    for o in q['o']:
        if not o[1]: continue  # an objective with no id in the source data
        if o[0]=='1': ob.append('k%sx%s'%(o[1],o[2]))
        elif o[0]=='2': ob.append('i%sx%s'%(o[1],o[2]))
        elif o[0]=='3': ob.append('o%s'%o[1])
        else: ob.append('a%s'%o[1])
    out.append('[%s]="%s|%d|%d|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s",'%(qid,esc(q['t']),q['l'],q['m'],ids(q['s']),ids(q['e']),','.join(q['p']),','.join(q['pa']),','.join(q['x']),','.join(ob),q['z'],q['r'],q['c'],q['f']))
out.append('}, n = {')
for k in sorted(N,key=int): out.append('[%s]="%s",'%(k,pl(N[k])))
out.append('}, o = {')
for k in sorted(O,key=int): out.append('[%s]="%s",'%(k,pl(O[k])))
out.append('}, i = {')
for k in sorted(I,key=int): out.append('[%s]="%s|%s",'%(k,esc(I[k][0]),','.join(I[k][1])))
out.append('} }')
open(sys.argv[2],'w',encoding='utf-8').write('\n'.join(out)+'\n')
print(len(Q),len(N),len(O),len(I))
