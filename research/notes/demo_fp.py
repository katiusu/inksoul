# -*- coding: utf-8 -*-
"""语法指纹 L1 最小可运行验证（jieba POS，无依存解析）"""
import jieba.posseg as pseg, itertools

NORM = {"不":"NEG","没":"NEG","没有":"NEG","别":"NEG","未":"NEG",
        "只":"ADV_LIM","只是":"ADV_LIM","仅仅":"ADV_LIM","不过":"ADV_LIM","就":"ADV_LIM","才":"ADV_LIM",
        "把":"PREP_BA","被":"PREP_BEI","让":"PREP_BEI","叫":"PREP_BEI","给":"PREP_BEI",
        "着":"ASP","了":"ASP","过":"ASP",
        "的":"DE_N","地":"DE_ADV","得":"DE_COMP"}
ANCHOR = {"NEG","ADV_LIM","PREP_BA","PREP_BEI","ASP","DE_N","DE_ADV","DE_COMP","CONJ","PART","QUANT"}
PUNCT = "，。？！；：、…—"

def norm(tag, w):
    if w in NORM: return NORM[w]
    if tag.startswith("r"): return "PRON"
    if tag.startswith("nr"): return "NAME"
    if tag.startswith("n"): return "N"
    if tag.startswith("v") or tag.startswith("V"): return "V"
    if tag.startswith("a"): return "A"
    if tag.startswith("d"): return "ADV"
    if tag.startswith("p"): return "PREP"
    if tag.startswith("c"): return "CONJ"
    if tag.startswith("m") or tag.startswith("q"): return "QUANT"
    if tag.startswith("u"): return "DE_N"
    return "OTHER"

def skel(s):
    out=[]
    for w,tag in pseg.cut(s):
        if w.strip()=="" : continue
        if all(ch in PUNCT for ch in w): out.append(w); continue
        if w in PUNCT: out.append(w); continue
        out.append(norm(tag,w))
    return out

def sub_cost(a,b):
    if a==b: return 0.0
    if a in ANCHOR or b in ANCHOR: return 1.0          # 功能锚点不容错
    if a in PUNCT or b in PUNCT: return 1.0
    return 0.15                                        # 内容槽近似等价

def wsim(a,b):
    """加权编辑距离相似度 (0~1)"""
    n,m=len(a),len(b)
    if n==0 and m==0: return 1.0
    D=[[0.0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): D[i][0]=i*1.0
    for j in range(m+1): D[0][j]=j*1.0
    for i in range(1,n+1):
        for j in range(1,m+1):
            D[i][j]=min(D[i-1][j]+1.0, D[i][j-1]+1.0, D[i-1][j-1]+sub_cost(a[i-1],b[j-1]))
    return 1.0 - D[n][m]/max(n,m)

PAIRS_SAME = [
 ("她没有回答，只是看着窗外。","他没有解释，只是低头整理衣袖。"),
 ("他推开门，走进屋里，坐在椅子上。","她拉开抽屉，拿出信封，放在桌上。"),
 ("风从窗口吹进来，吹动了桌上的纸。","雨从屋檐落下来，打湿了门口的台阶。"),
 ("他知道自己错了，却始终没开口。","她明白事情败了，只是一直没抬头。"),
 ("屋子里很安静，只有挂钟在走。","巷子里很暗，只有远处有一点灯。"),
]
PAIRS_DIFF = [
 ("她没有回答，只是看着窗外。","因为昨天下过雨，路面还是湿的。"),
 ("她知道自己错了，却始终没开口。","请把那本书递给我。"),
 ("屋子里很安静，只有挂钟在走。","他比她高半个头。"),
 ("风从窗口吹进来，吹动了桌上的纸。","如果明天不下雨，我们就去趟城里。"),
 ("他推开门，走进屋里，坐在椅子上。","那张桌子是去年从旧货市场买回来的。"),
]

def run(name,pairs,th=0.75):
    ok=0
    for a,b in pairs:
        sa,sb=skel(a),skel(b); s=wsim(sa,sb)
        pred = s>=th
        gold = (name=="same")
        ok += (pred==gold)
        print(f"[{name}] {s:.3f} gold={gold} pred={pred} :: {' '.join(sa)}  ||  {' '.join(sb)}")
    print(f"-- {name}: {ok}/{len(pairs)} = {ok/len(pairs):.0%}\n")
    return ok

print("=== 实例 ===")
for a,b in PAIRS_SAME[:1]+PAIRS_DIFF[:1]:
    print(a); print(' '.join(skel(a)))
    print(b); print(' '.join(skel(b)))
    print('sim=',round(wsim(skel(a),skel(b)),3)); print()
print("=== 批量 ===")
r1=run("same",PAIRS_SAME); r2=run("diff",PAIRS_DIFF)
print(f"TOTAL: {r1+r2}/{len(PAIRS_SAME)+len(PAIRS_DIFF)} = {(r1+r2)/10:.0%}")
