#!/usr/bin/env python3
"""稳健核实: 依次尝试 OpenAlex / Crossref / arXiv，带退避。输出到 stdout 与 ledger_auto.md"""
import sys, json, time, urllib.parse, urllib.request
UA={"User-Agent":"InkSoul-research/1.0 (mailto:research@example.org)"}
def get(u, t=45):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t).read().decode("utf-8","replace")
def oa(q, n=3):
    u="https://api.openalex.org/works?search=%s&per_page=%d&select=title,doi,publication_year,primary_location,cited_by_count,type,authorships"%(urllib.parse.quote(q),n)
    d=json.loads(get(u)); out=[]
    for w in d.get("results",[]):
        src=((w.get("primary_location") or {}).get("source") or {})
        out.append({"t":w.get("title"),"y":w.get("publication_year"),"doi":(w.get("doi") or "").replace("https://doi.org/",""),"v":src.get("display_name"),"c":w.get("cited_by_count"),"ty":w.get("type"),"a":[x["author"]["display_name"] for x in (w.get("authorships") or [])][:6]})
    return out
def cr(q,n=3):
    u="https://api.crossref.org/works?query.bibliographic=%s&rows=%d&select=title,DOI,issued,container-title,author,type"%(urllib.parse.quote(q),n)
    d=json.loads(get(u)); out=[]
    for it in d.get("message",{}).get("items",[]):
        out.append({"t":(it.get("title") or [""])[0],"y":(it.get("issued",{}).get("date-parts") or [[None]])[0][0],"doi":it.get("DOI"),"v":(it.get("container-title") or [""])[0],"ty":it.get("type"),"a":[" ".join(filter(None,[a.get("given"),a.get("family")])) for a in (it.get("author") or [])][:6]})
    return out
def ax(q,n=3):
    u="https://export.arxiv.org/api/query?search_query=ti:%s&max_results=%d"%(urllib.parse.quote('"%s"'%q),n)
    import re; x=get(u); out=[]
    for e in re.findall(r"<entry>(.*?)</entry>",x,re.S):
        g=lambda tag:(re.search(r"<%s>(.*?)</%s>"%(tag,tag),e,re.S) or [None,None])[1]
        out.append({"t":" ".join((g("title") or "").split()),"y":(g("published") or "")[:4],"arxiv":(g("id") or "").split("/abs/")[-1],"a":re.findall(r"<name>(.*?)</name>",e)[:6]})
    return out
qs=[l.strip() for l in open(sys.argv[1],encoding="utf-8") if l.strip()]
buf=["# 自动核实台账（verify2.py）\n"]
for q in qs:
    buf.append("\n## %s\n"%q)
    got=False
    for fn,name in ((oa,"OPENALEX"),(cr,"CROSSREF"),(ax,"ARXIV")):
        for attempt in range(3):
            try:
                r=fn(q)
                if r:
                    buf.append("- **%s**"%name)
                    for x in r[:3]: buf.append("  - `%s`"%json.dumps(x,ensure_ascii=False))
                    got=True; break
                time.sleep(2)
            except Exception as e:
                buf.append("- %s err(attempt%d): %s"%(name,attempt+1,str(e)[:80]))
                time.sleep(4+attempt*4)
        if got: break
        time.sleep(1.5)
    time.sleep(3)
open("/sdcard/Project/InkSoul/research/ledger_auto.md","w",encoding="utf-8").write("\n".join(buf))
print("\n".join(buf))
