from collections import deque, Counter
import pandas as pd
import numpy as np
import math
from deepgo.constants import (
    BIOLOGICAL_PROCESS,
    MOLECULAR_FUNCTION,
    CELLULAR_COMPONENT,
    FUNC_DICT,
    NAMESPACES)


class Ontology(object):

    def __init__(self, filename='data/go.obo', with_rels=True):
        self.ont = self.load(filename, with_rels)
        self.ic = None

    def has_term(self, term_id):
        return term_id in self.ont

    def is_root_term(self, term_id):
        return (term_id == BIOLOGICAL_PROCESS
                or term_id == MOLECULAR_FUNCTION
                or term_id == CELLULAR_COMPONENT)

    def calculate_ic(self, annots):
        cnt = Counter()
        for x in annots:
            cnt.update(x)
        self.ic = {}
        for go_id, n in cnt.items():
            parents = self.get_parents(go_id)
            if len(parents) == 0:
                min_n = n
            else:
                min_n = min([cnt[x] for x in parents])
            self.ic[go_id] = math.log(min_n / n, 2)
    
    def get_ic(self, go_id):
        if self.ic is None:
            raise Exception('Not yet calculated')
        if go_id not in self.ic:
            return 0.0
        return self.ic[go_id]

    def get(self, term_id):
        return self.ont[term_id]


    def load(self, filename, with_rels):
        ont = dict()
        obj = None
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line == '[Term]':
                    if obj is not None:
                        ont[obj['id']] = obj
                    obj = dict()
                    obj['is_a'] = list()
                    obj['part_of'] = list()
                    obj['regulates'] = list()
                    obj['alt_ids'] = list()
                    obj['consider'] = list()
                    obj['replaced_by'] = None
                    obj['is_obsolete'] = False
                    continue
                elif line == '[Typedef]':
                    obj = None
                else:
                    if obj is None:
                        continue
                    l = line.split(": ")
                    if l[0] == 'id':
                        obj['id'] = l[1]
                    elif l[0] == 'alt_id':
                        obj['alt_ids'].append(l[1])
                    elif l[0] == 'namespace':
                        obj['namespace'] = l[1]
                    elif l[0] == 'is_a':
                        obj['is_a'].append(l[1].split(' ! ')[0])
                    elif with_rels and l[0] == 'relationship':
                        it = l[1].split()
                        # add all types of relationships
                        obj['is_a'].append(it[1])
                    elif l[0] == 'name':
                        obj['name'] = l[1]
                    elif l[0] == 'replaced_by':
                        obj['replaced_by'] = l[1].split(' ! ')[0]
                    elif l[0] == 'consider':
                        obj['consider'].append(l[1].split(' ! ')[0])
                    elif l[0] == 'is_obsolete' and l[1] == 'true':
                        obj['is_obsolete'] = True
        if obj is not None:
            ont[obj['id']] = obj
        # Keep obsolete terms out of the active ontology, but remember their
        # replaced_by/consider successors so predicted-but-obsolete classes can be
        # transferred (or flagged) at display time instead of silently dropped.
        self.obsolete = {}
        for term_id in list(ont.keys()):
            for t_id in ont[term_id]['alt_ids']:
                ont[t_id] = ont[term_id]
            if ont[term_id]['is_obsolete']:
                o = ont[term_id]
                self.obsolete[term_id] = {
                    'name': o.get('name', ''),
                    'namespace': o.get('namespace'),
                    'replaced_by': o.get('replaced_by'),
                    'consider': list(o.get('consider', [])),
                }
                del ont[term_id]
        for term_id, val in ont.items():
            if 'children' not in val:
                val['children'] = set()
            for p_id in val['is_a']:
                if p_id in ont:
                    if 'children' not in ont[p_id]:
                        ont[p_id]['children'] = set()
                    ont[p_id]['children'].add(term_id)
        return ont


    def get_anchestors(self, term_id):
        if term_id not in self.ont:
            return set()
        term_set = set()
        q = deque()
        q.append(term_id)
        while(len(q) > 0):
            t_id = q.popleft()
            if t_id not in term_set:
                term_set.add(t_id)
                for parent_id in self.ont[t_id]['is_a']:
                    if parent_id in self.ont:
                        q.append(parent_id)
        return term_set


    def get_parents(self, term_id):
        if term_id not in self.ont:
            return set()
        term_set = set()
        for parent_id in self.ont[term_id]['is_a']:
            if parent_id in self.ont:
                term_set.add(parent_id)
        return term_set


    def get_namespace_terms(self, namespace):
        terms = set()
        for go_id, obj in self.ont.items():
            if obj['namespace'] == namespace:
                terms.add(go_id)
        return terms

    def get_namespace(self, term_id):
        if term_id in self.ont:
            return self.ont[term_id]['namespace']
        info = getattr(self, 'obsolete', {}).get(term_id)
        if info is not None:
            return info.get('namespace')
        return None

    def resolve_term(self, term_id):
        """Resolve a predicted GO id for display, accounting for obsoletion.

        Returns ``(target_id, status, label)``:
          * active term            -> (term_id, 'active', name)
          * obsolete + replaced_by -> (replacement, 'replaced', 'name (was GO:x, obsolete)')
          * obsolete + consider    -> (suggestion, 'consider', 'name (GO:x obsolete; consider)')
          * obsolete, no successor -> (term_id, 'obsolete', 'name [OBSOLETE]')
          * unknown id             -> (None, 'unknown', '')
        ``target_id`` is the id to score/propagate under; ``label`` is the display text.
        """
        ont = self.ont
        if term_id in ont and not ont[term_id].get('is_obsolete'):
            return term_id, 'active', ont[term_id].get('name', term_id)
        info = getattr(self, 'obsolete', {}).get(term_id)
        if info is None:
            return None, 'unknown', ''
        rep = info.get('replaced_by')
        if rep and rep in ont:
            return rep, 'replaced', f"{ont[rep].get('name', rep)} (was {term_id}, obsolete)"
        for c in info.get('consider', []):
            if c in ont:
                return c, 'consider', f"{ont[c].get('name', c)} ({term_id} obsolete; consider)"
        return term_id, 'obsolete', (info.get('name') or term_id) + ' [OBSOLETE]'
    
    def get_term_set(self, term_id):
        if term_id not in self.ont:
            return set()
        term_set = set()
        q = deque()
        q.append(term_id)
        while len(q) > 0:
            t_id = q.popleft()
            if t_id not in term_set:
                term_set.add(t_id)
                for ch_id in self.ont[t_id]['children']:
                    q.append(ch_id)
        return term_set

def read_fasta(lines):
    seqs = list()
    info = list()
    seq = ''
    inf = ''
    for line in lines:
        line = line.strip()
        if line.startswith('>'):
            if seq != '':
                seqs.append(seq)
                info.append(inf)
                seq = ''
            inf = line[1:]
        else:
            seq += line
    seqs.append(seq)
    info.append(inf)
    return info, seqs


def acc2id(acc_id):
    res = 0
    base = 36
    for c in acc_id:
        if c.isdigit():
            res = res * base + (ord(c) - ord('0'))
        else:
            res = res * base + (ord(c) - ord('A') + 10)
    return res
