import re,subprocess,os
COL=3.347; FULL=6.972          # IEEE Access measures, inches
s=open('access_paper.tex',encoding='utf-8').read()
b=s.split(r'\begin{thebibliography}')[0]
print(f"{'LABEL':22s} {'ENV':8s} {'src_w_in':>8s} {'target':>7s} {'scale':>6s} {'8pt->':>6s}  verdict")
print('-'*82)
todo=[]
for m in re.finditer(r'\\begin\{(figure\*?)\}(.*?)\\end\{\1\}', b, re.S):
    env, inner = m.group(1), m.group(2)
    lab=re.search(r'\\label\{([^}]+)\}',inner); img=re.search(r'\\includegraphics\[[^\]]*\]\{([^}]+)\}',inner)
    if not img: continue
    f=img.group(1)
    out=subprocess.run(['pdfinfo',f],capture_output=True,text=True).stdout
    ps=re.search(r'Page size:\s+([0-9.]+) x ([0-9.]+)',out)
    if not ps: continue
    srcw=float(ps.group(1))/72.0
    tgt = FULL if env.endswith('*') else COL
    sc = tgt/srcw
    eff = 8*sc
    v='OK' if eff>=6.0 else ('TIGHT' if eff>=5.0 else 'TOO SMALL')
    if v!='OK' and not env.endswith('*'):
        todo.append(lab.group(1))
    print(f"{lab.group(1):22s} {env:8s} {srcw:8.2f} {tgt:7.2f} {sc:6.2f} {eff:6.1f}pt  {v}")
print("\npromote to figure*:", todo)
