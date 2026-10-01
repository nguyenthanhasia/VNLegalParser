from __future__ import annotations
import json, random, re, sys
from pathlib import Path
from vietnamese_legal_parser import parse_structure

def walk(nodes):
    for n in nodes:
        yield n; yield from walk(n.get('children',[]))

def got(text):
    out={}
    for n in walk(parse_structure(text)):
        out.setdefault(n['element_type'],[]).append(n['number'])
    return out

def check(text, exp):
    g=got(text)
    for t in ['part','chapter','section','subsection','division','article','clause','point']:
        if t in exp and g.get(t,[]) != exp[t]: return False
    for x in exp.get('forbid_clause',[]):
        if x in g.get('clause',[]): return False
    return True

def mutate(text, kind, rnd):
    lines=text.splitlines()
    if kind=='whitespace':
        return '\n'.join(' '*rnd.randint(0,3)+x+' '*rnd.randint(0,3) for x in lines)
    if kind=='unicode':
        return text.replace(' ', '\u00a0' if rnd.random()<.5 else '\u2009')
    if kind=='html_wrapped':
        return '\n'.join(f'<p>{x}</p>' for x in lines)
    if kind=='markdown_noise':
        return '\n'.join(('## '+x if re.match(r'\s*(Phần|Chương|Mục|Tiểu mục|Tiết|Điều)\b',x,re.I) else x) for x in lines)
    if kind=='marker_case_punct':
        out=[]
        for x in lines:
            if rnd.random()<.5 and re.match(r'\s*(Phần|Chương|Mục|Tiểu mục|Tiết|Điều)\b',x,re.I): x=x.swapcase()
            out.append(x)
        return '\n'.join(out)
    if kind=='flattened': return ' '.join(x.strip() for x in lines if x.strip())
    if kind=='partial_line_loss':
        out=[]
        for x in lines:
            if out and rnd.random()<.28: out[-1] += ' ' + x.strip()
            else: out.append(x)
        return '\n'.join(out)
    if kind=='mixed':
        s='\n'.join(' '*rnd.randint(0,2)+x for x in lines)
        if rnd.random()<.6: s=s.replace(' ','\u00a0')
        ls=s.splitlines(); out=[]
        for x in ls:
            if out and rnd.random()<.18: out[-1]+=' '+x.strip()
            else: out.append(x)
        return '\n'.join(out)
    return text

def main(path):
    data=json.loads(Path(path).read_text())
    data=[x for x in data if x.get('source_url','').startswith('http') and x['id'] not in {'actual_annex_heading','annex_2026_table_like_content'}]
    kinds=['whitespace','unicode','html_wrapped','markdown_noise','marker_case_punct','flattened','partial_line_loss','mixed']
    res={k:[0,0] for k in kinds}
    for ci,c in enumerate(data):
        for k in kinds:
            for j in range(25):
                rnd=random.Random(20261001 + ci*100000 + kinds.index(k)*1000+j)
                ok=check(mutate(c['content'],k,rnd), c['expect'])
                res[k][1]+=1; res[k][0]+=int(ok)
    total=sum(v[1] for v in res.values()); passed=sum(v[0] for v in res.values())
    print(json.dumps({'cases':len(data),'passed':passed,'total':total,'rate':passed/total,'by_kind':{k:{'passed':v[0],'total':v[1],'rate':v[0]/v[1]} for k,v in res.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__': main(sys.argv[1])
