from wc_rules import bioschema as bio
import unittest

class TestBioschema(unittest.TestCase):
	
	def test_site(self):
		class A(bio.Site):pass
		a = A()
		self.assertEqual(a.label,'A')
		
		a.set_id('1')
		self.assertEqual(a.id,'1')
		
		with self.assertRaises(bio.AddObjectError): a.add(object())
		
	def test_bond(self):
		class A(bio.Site):pass
		class B(bio.Site):pass
		a,b = A(), B()
		
		self.assertEqual([x.bond for x in [a,b]],[None,None])
		self.assertEqual([x.bound for x in [a,b]],[False,False])
		
		bnd = bio.Bond(sites=[a,b])
		self.assertEqual([x.label for x in bnd.sites],['A','B'])
		self.assertEqual([x.bound for x in bnd.sites],[True,True])
		
		bnd = bio.Bond().add([a,b])
		self.assertEqual([x.label for x in bnd.sites],['A','B'])
		
		bnd = bio.Bond().add(a).add(b)
		self.assertEqual([x.label for x in bnd.sites],['A','B'])
		
		bnd.set_id('1')
		self.assertEqual(bnd.id,'1')
		
		with self.assertRaises(bio.AddObjectError): bnd.add(object())
		
		a = bnd.sites.get(label='A')
		self.assertEqual(a.label,'A')
		
	def test_exclusion(self):
		class A(bio.Site):pass
		class B(bio.Site):pass
		class C(bio.Site):pass
		a,b,c = A(), B(), C()
		
		exc = bio.Exclusion().add([a,c])
		self.assertEqual(c.available_to_bind,True)
		self.assertEqual([x.label for x in exc.sites],['A','C'])
		self.assertEqual([y.label for x in exc.sites for y in x.get_excludes() ], ['C','A'] )
		
		bnd  = bio.Bond().add([a,b])
		self.assertEqual(c.available_to_bind,False)
		
		exc.set_id('1')
		self.assertEqual(exc.id,'1')
		
		with self.assertRaises(bio.AddObjectError): exc.add(object())
		
		a = exc.sites.get(label='A')
		self.assertEqual(a.label,'A')
		
	def test_state(self):
		class A(bio.Site):pass
		class P(bio.BooleanStateVariable):pass
		a,p = A(), P()
		self.assertEqual(p.label,'P')
		
		p.set_id('1')
		self.assertEqual(p.id,'1')
		
		a.add(p)
		self.assertEqual([x.label for x in a.boolvars],['P'])
		
		p.set_true()
		self.assertEqual(p.value,True)
		
		p.set_false()
		self.assertEqual(p.value,False)
		
	def test_molecule(self):
		class A(bio.Molecule):pass
		class B(bio.Site):pass
		class C(bio.Site):pass
		a,b,c = A(), B(), C()
		self.assertEqual(a.label,'A')
		
		a.add([b,c])
		self.assertEqual([x.label for x in a.sites],['B','C'])
		
		a.set_id('1')
		self.assertEqual(a.id,'1')
		
		exc = bio.Exclusion().add([b,c])
		a = A().add(b).add(c).add(exc)
		self.assertEqual([x.label for x in a.sites],['B','C'])
		self.assertEqual([x.label for x in a.exclusions[0].sites],['B','C'])
		
		with self.assertRaises(bio.AddObjectError): a.add(object())
		
		b = a.sites.get(label='B')
		self.assertEqual(b.label,'B')
		b = exc.sites.get(label='B')
		self.assertEqual(b.label,'B')
		
	def test_complex(self):
		class A(bio.Molecule):pass
		class B(bio.Site):pass
		a1,a2,b1,b2 = A().set_id('1'), A().set_id('2'), B().set_id('1'), B().set_id('2')
		a1.add(b1)
		a2.add(b2)
		bnd = bio.Bond().add([b1,b2])
		
		cplx = bio.Complex().add([a1,a2,bnd])
		self.assertEqual([x.label for x in cplx.molecules],['A','A'])
		self.assertEqual([x.label for bnd in cplx.bonds for x in bnd.sites],['B','B'])
		
		cplx = bio.Complex().add(a1).add(a2).add(bnd)
		self.assertEqual([x.label for x in cplx.molecules],['A','A'])
		self.assertEqual([x.label for bnd in cplx.bonds for x in bnd.sites],['B','B'])
		
		cplx.set_id('1')
		self.assertEqual(cplx.id,'1')
		
		with self.assertRaises(bio.AddObjectError): cplx.add(object())
		
		a = cplx.molecules.get(label='A',id='1')
		self.assertEqual([a.label,a.id],['A','1'])
		
		b = cplx.bonds.get().sites.get(label='B',id='1')
		self.assertEqual([b.label,b.id],['B','1'])
		
	def test_bond_op(self):
		class A(bio.Site):pass
		a1,a2 = A().set_id('1'), A().set_id('2')
		bnd_op = bio.BondOperation().set_target([a1,a2])
		self.assertEqual([x.label for x in bnd_op.target],['A','A'])
		
		with self.assertRaises(bio.AddObjectError): bnd_op.set_target(object())
		
	def test_state_op(self):
		class P(bio.BooleanStateVariable):pass
		p = P()
		state_op = bio.BooleanStateOperation().set_target(p)
		self.assertEqual(state_op.target.label,'P')
		
		with self.assertRaises(bio.AddObjectError): state_op.set_target(object())
		with self.assertRaises(bio.AddObjectError): state_op.set_target([object(),])	
	
	def test_rule(self):
		class A(bio.Molecule): pass
		class B(bio.Molecule): pass
		class b(bio.Site): pass
		class a(bio.Site): pass
		class P(bio.BooleanStateVariable):pass
		
		a1 = a()
		b1 = b().add( P() )
		A1 = A().add( a1  )
		B1 = B().add( b1  )
		
		reac1 = bio.Complex().add(A1)
		reac2 = bio.Complex().add(B1)
		op1 = bio.AddBond().set_target([a1,b1])
		op2 = bio.Phosphorylate().set_target(b1.boolvars.get())
		
		rule1 = bio.Rule(reversible=True).add([reac1,reac2,op1,op2])
 		
		self.assertEqual([x.label for y in rule1.reactants for x in y.molecules],['A','B'])
		self.assertEqual([y.label for y in rule1.operations[0].target],['a','b'])
		self.assertEqual(rule1.operations[1].target.label,'P')
		
