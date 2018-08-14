import networkx as nx
from wc_rules.indexer import Index_By_ID
from utils import AddError, generate_id
import matplotlib.pyplot as plt
import pprint
import operator as op
from collections import defaultdict
from itertools import chain

class Token(dict):
    ''' Each token is a dict whose keys are pattern node ids
    and values are wmg node ids '''

    def __init__(self,**kwargs):
        self['tag'] = kwargs.pop('tag')
        self['species'] = kwargs.pop('species')
        for kwarg in kwargs:
            self[kwarg] = kwargs[kwarg]


class Matcher(object):
    def __init__(self):
        self.rete_net = nx.DiGraph()
        self.rete_net.add_node('root', data=Root())
        self._patterns = Index_By_ID()
        self.map_pattern_to_rete_nodes = dict()

    # Rete net basic operations
    def get_rete_node(self,idx):
        return self.rete_net.node[idx]['data']

    def append_rete_node(self,node):
        self.rete_net.add_node(node.id,data=node)
        return self

    def append_rete_edge(self,node1,node2):
        self.rete_net.add_edge(node1.id,node2.id)
        return self

    def get_rete_successors(self,node):
        x = list(self.rete_net.successors(node.id))
        return [self.get_rete_node(idx) for idx in x]

    def filter_rete_successors(self,node,attr=None,value=None):
        x = self.get_rete_successors(node)
        if (attr,value)==(None,None): return x
        return [z for z in x if getattr(z,attr,None)==value]

    def check_attribute_and_add_successor(self,current_node,_class_to_init,attr=None,value=None):
        # works only for nodes with single argument instantiations
        existing_successors = self.filter_rete_successors(current_node,attr,value)
        if len(existing_successors)==0:
            new_node = _class_to_init(value)
            self.append_rete_node(new_node)
            self.append_rete_edge(current_node,new_node)
            return new_node
        elif len(existing_successors)==1:
            return existing_successors[0]
        else:
            utils.GenericError('Duplicates on the Rete net. Bad!')
        return None

    def add_mergenode(self,node1,node2):
        varname_set = set()
        for name in node1.variable_names:
            varname_set.add(name)
        for name in node2.variable_names:
            varname_set.add(name)
        varnames = tuple(sorted(list(varname_set)))
        new_node = merge(varnames)
        self.append_rete_node(new_node)
        self.append_rete_edge(node1,new_node)
        self.append_rete_edge(node2,new_node)
        return new_node

    def draw_rete_net(self):
        labels_dict = dict()
        for n,node in enumerate(self.rete_net.nodes):
            labels_dict[node] = ''.join(['(',str(n),') ',str(self.get_rete_node(node))])
        g1 = nx.relabel_nodes(self.rete_net,labels_dict)
        nx.write_gml(g1, "rete.gml",stringizer=str)
        return self

    # Rete net advanced operations
    def add_checkTYPE_path(self,current_node,type_vec):
        for (kw,_class) in type_vec:
            current_node = self.check_attribute_and_add_successor(current_node,checkTYPE,'_class',_class)
        return current_node

    def add_checkATTR_path(self,current_node,attr_vec):
        new_tuples = sorted([tuple(x[1:]) for x in attr_vec])
        for attr_tuple in new_tuples:
            current_node = self.check_attribute_and_add_successor(current_node,checkATTR,'attr_tuple',attr_tuple)
        return current_node

    def add_store(self,current_node):
        existing_successors = self.get_rete_successors(current_node)
        existing_stores = [x for x in existing_successors if isinstance(x,store)]
        if len(existing_stores) == 1:
            current_node = existing_stores[0]
        elif len(existing_stores) == 0:
            new_node = store()
            self.append_rete_node(new_node)
            self.append_rete_edge(current_node,new_node)
            current_node = new_node
        else:
            raise utils.GenericError('Duplicates on the Rete net! Bad!')
        return current_node

    def add_aliasNODE(self,current_node,varname):
        var = (varname,)
        current_node = self.check_attribute_and_add_successor(current_node,alias,'variable_names',var)
        return current_node

    def add_checkEDGETYPE(self,current_node,attr1,attr2):
        attrpair = tuple([attr1,attr2])
        current_node = self.check_attribute_and_add_successor(current_node,checkEDGETYPE,'attribute_pair',attrpair)
        return current_node

    def add_aliasEDGE(self,current_node,var1,var2):
        varnames = (var1,var2)
        current_node = self.check_attribute_and_add_successor(current_node,alias,'variable_names',varnames)
        return current_node

    def add_mergenode_path(self,list_of_nodes):
        current_node = list_of_nodes.pop(0)
        for node in list_of_nodes:
            new_node = node
            merge_node = self.add_mergenode(current_node,new_node)
            current_node = merge_node
        return current_node

    def add_aliasPATTERN(self,current_node,name):
        alias_node = alias((name,))
        self.append_rete_node(alias_node)
        self.append_rete_edge(current_node,alias_node)
        current_node = alias_node
        return current_node

    # Matcher-level operations
    def add_pattern(self,pattern):
        if pattern in self._patterns:
            raise utils.AddError('Multiple patterns with same ID found.')
        self._patterns.append(pattern)
        pattern_node = self.compile_pattern(pattern)
        self.map_pattern_to_rete_nodes[pattern.id] = pattern_node
        return self

    def compile_pattern(self,pattern):
        ''' Steps through the queries generated by a pattern and increments the Rete net. '''
        qdict = pattern.generate_queries()
        varnames = sorted(qdict['type'].keys())
        new_varnames = { v:str(pattern.id+':'+v) for v in varnames }
        vartuple_nodes = defaultdict(set)

        for var in varnames:
            # compile types
            type_vec = qdict['type'][var]
            attr_vec = qdict['attr'][var]
            new_varname = new_varnames[var]
            # for each variable (i.e. each node in the pattern)
            # start from root, add checkTYPE(s), checkATTR(s), store and varname_node
            current_node = self.get_rete_node('root')
            current_node = self.add_checkTYPE_path(current_node,type_vec)
            current_node = self.add_checkATTR_path(current_node,attr_vec)
            current_node = self.add_store(current_node)
            current_node = self.add_aliasNODE(current_node,new_varname)
            vartuple_nodes[(new_varname,)].add(current_node)

        for rel in qdict['rel']:
            (kw,var1,attr1,attr2,var2) = rel
            current_node = self.get_rete_node('root')
            current_node = self.add_checkEDGETYPE(current_node,attr1,attr2)
            current_node = self.add_store(current_node)
            var1_new = new_varnames[var1]
            var2_new = new_varnames[var2]
            current_node = self.add_aliasEDGE(current_node,var1_new,var2_new)
            vartuple_nodes[(var1_new,var2_new)].add(current_node)

        # compute local subgraphs (1-deep) for each variable
        merge_nodes = list()
        for old_name,var in new_varnames.items():
            vartuples = sorted(x for x in vartuple_nodes if var in x)
            vartuple_nodelist = list(chain(*[vartuple_nodes[x] for x in vartuples]))
            current_node = self.add_mergenode_path(vartuple_nodelist)
            merge_nodes.append(current_node)

        # put together local subgraphs
        current_node = self.add_mergenode_path(merge_nodes)
        current_node = self.add_aliasPATTERN(current_node,pattern.id)

        return current_node

class ReteNode(object):
    def __init__(self,id=None):
        if id is None:
            self.id = generate_id()
            self.archetype = ''

class SingleInputNode(ReteNode): pass

class Root(SingleInputNode):
    def __init__(self):
        self.id = 'root'
        self.archetype='root'

    def __str__(self):
        return 'root'

class check(SingleInputNode):
    def __init__(self,id=None):
        super().__init__(id)
        self.archetype = 'check'

class checkTYPE(check):
    def __init__(self,_class,id=None):
        super().__init__(id)
        self._class = _class

    def __str__(self):
        return 'isinstance(*,'+self._class.__name__+')'

class checkATTR(check):
    operator_dict = {
    'lt':'<', 'le':'<=',
    'eq':'==', 'ne':'!=',
    'ge':'>=', 'gt':'>',
    }
    def __init__(self,attr_tuple,id=None):
        super().__init__(id)
        self.attr_tuple = attr_tuple

    def __str__(self):
        attrname = self.attr_tuple[0]
        opname = self.operator_dict[self.attr_tuple[1].__name__]
        value = str(self.attr_tuple[2])
        return ''.join(['*.',attrname,opname,value])

class store(SingleInputNode):
    def __init__(self,id=None):
        super().__init__(id)
        self.archetype = 'store'

    def __str__(self):
        return 'store'

class alias(SingleInputNode):
    def __init__(self,var_tuple,id=None):
        super().__init__(id)
        self.archetype = 'alias'
        self.variable_names = var_tuple

    def __str__(self):
        return ','.join(list(self.variable_names))

class checkEDGETYPE(check):
    def __init__(self,attrpair,id=None):
        super().__init__(id)
        self.attribute_pair = attrpair

    def __str__(self):
        v = ['*'+str(i)+'.'+x for i,x in enumerate(self.attribute_pair)]
        return '--'.join(v)

class merge(ReteNode):
    def __init__(self,var_tuple,id=None):
        super().__init__(id)
        self.variable_names = var_tuple
        self.archetype = 'merge'

    def __str__(self):
        return ','.join(self.variable_names)

def main():
    from wc_rules.chem import Molecule, Site, Bond
    from wc_rules.pattern import Pattern
    from wc_rules.species import Species
    from obj_model import core

    class A(Molecule):pass
    class X(Site):
        ph = core.BooleanAttribute(default=None)
        v = core.IntegerAttribute(default=None)

    p1 = Pattern('p1').add_node( A(id='A').add_sites(X(id='x',ph=True,v=0)) )
    p2 = Pattern('p2').add_node( A(id='A').add_sites(X(id='x',ph=True)) )
    p3 = Pattern('p3').add_node( A(id='A').add_sites(X(id='x')) )

    bnd = Bond(id='bnd')
    a1 = A(id='A1').add_sites(X(id='x1',ph=True,v=0).set_bond(bnd))
    a2 = A(id='A2').add_sites(X(id='x2',ph=True,v=1).set_bond(bnd))
    p4 = Pattern('p4').add_node(a1)

    m = Matcher()
    for p in [p1,p2,p3,p4]:
        m.add_pattern(p)
    m.draw_rete_net()


if __name__ == '__main__':
    main()