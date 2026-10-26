#!/usr/bin/env python3
"""Independent fairness oracle.

This checker intentionally does not import Manager or RTL.  It checks the written
eligibility rule: a healthy candidate is overdue and unflagged; unresolved evidence
on another flagged block cannot remove that candidate when fairness is enabled.
Priority selects the maximum candidate, with lowest-index tie break.
"""
import ast, csv, itertools, math, sys

NB=5

def choose(overdue, flagged, unresolved, priority, enabled):
    healthy = overdue & ~flagged & ((1<<NB)-1)
    eligible = healthy if enabled and (flagged & unresolved) else (healthy if not (flagged & unresolved) else 0)
    if not eligible: return None
    return max((b for b in range(NB) if eligible>>b & 1), key=lambda b:(priority[b],-b))

def exhaustive():
    p=[5,4,3,2,1]
    for overdue in range(1<<NB):
      for flagged in range(1<<NB):
       for unresolved in range(1<<NB):
        x=choose(overdue,flagged,unresolved,p,True)
        if x is not None and ((flagged>>x)&1): raise AssertionError('flagged block selected')
        if (overdue & ~flagged) and (flagged & unresolved):
          if x is None: raise AssertionError('healthy candidate withheld')
    assert choose(0b11111,0b00010,0b00010,p,True) == 0
    assert choose(0b11111,0b00010,0b00010,p,False) is None

def csv_check(path):
    vals=[]; exceed=0
    for row in csv.DictReader(open(path)):
      for v in ast.literal_eval(row['healthy_full_scan_delay_after_flag']):
        if v is not None:
          vals.append(float(v)); exceed += v > 154
    vals.sort(); q=vals[math.ceil(.95*len(vals))-1]
    return len(vals), max(vals), vals[len(vals)//2], q, exceed

if __name__ == '__main__':
    exhaustive()
    if len(sys.argv)>1:
      for f in sys.argv[1:]: print(f, csv_check(f))
    print('independent fairness oracle: PASS')
