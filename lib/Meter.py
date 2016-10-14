from tools import *
#from Queue import Queue
from MeterConstraint import MeterConstraint as Constraint
from MeterSlot import MeterSlot as Slot
from MeterPosition import MeterPosition as Position
from Parse import Parse, Bounding
from copy import copy
from tools import makeminlength
from entity import being
import os


def genDefault():
	import prosodic
	metername = sorted(prosodic.config['meters'].keys())[0]
	meter=prosodic.config['meters'][metername]
	print '>> no meter specified. defaulting to this meter:'
	print meter
	return meter
	

#def meterShakespeare():
#	return Meter('strength.s=>')







class Meter:
	Weak="w"
	Strong="s"
	## for caching meter-parses
	parseDict = {}

	@staticmethod
	def genMeters():
		meterd={}
		meterd['*StrongSyllableWeakPosition [Shakespeare]']=Meter(['strength.w=>-p/1'], (1,2), False)
		meterd['*WeakSyllableStrongPosition']=Meter(['strength.s=>-u/1'], (1,2), False)
		meterd['*StressedSyllableWeakPosition']=Meter(['stress.w=>-p/1'], (1,2), False)
		meterd['*UnstressedSyllableStrongPosition [Hopkins]']=Meter(['stress.s=>-u/1'], (1,2), False)
		return meterd

	def __str__(self):
		#constraints = '\n'.join(' '.join([slicex) for slicex in slice() )
		#constraint_slices=slice(self.constraints,slice_length=3,runts=True)
		constraint_slices={}
		for constraint in self.constraints:
			ckey=constraint.name.replace('-','.').split('.')[0]
			if not ckey in constraint_slices:
				constraint_slices[ckey]=[]
			constraint_slices[ckey]+=[constraint]
		constraint_slices = [constraint_slices[k] for k in sorted(constraint_slices)]
		constraints = '\n\t\t'.join(' '.join(c.name_weight for c in slicex) for slicex in constraint_slices)

		x='<<Meter\n\tID: {5}\n\tName: {0}\n\tConstraints: \n\t\t{1}\n\tMaxS, MaxW: {2}, {3}\n\tAllow heavy syllable split across two positions: {4}\n>>'.format(self.name, constraints, self.posLimit[0], self.posLimit[1], bool(self.splitheavies), self.id)
		return x
	
	@property
	def constraint_nameweights(self):
		return ' '.join(c.name_weight for c in self.constraints)

	#def __init__(self,constraints=None,posLimit=(2,2),splitheavies=False,name=None):
	def __init__(self,config):
		#self.type = type
		constraints=config['constraints']
		self.posLimit=(config['maxS'],config['maxW'])
		self.constraints = []
		self.splitheavies=config['splitheavies']
		self.name=config.get('name','')
		self.id = config['id']
		import prosodic
		self.config=prosodic.config
		
		if not constraints:
			self.constraints.append(Constraint(0,"foot-min",None,1))
			self.constraints.append(Constraint(1,"strength.s=>p",None,1))
			self.constraints.append(Constraint(2,"strength.w=>u",None,1))
			self.constraints.append(Constraint(3,"stress.s=>p",None,1))
			self.constraints.append(Constraint(4,"stress.w=>u",None,1))
			self.constraints.append(Constraint(5,"weight.s=>p",None,1))
			self.constraints.append(Constraint(6,"weight.w=>u",None,1))

		elif type(constraints) == type([]):
			for i in range(len(constraints)):
				c=constraints[i]
				if "/" in c:
					(cname,cweight)=c.split("/")
					#cweight=int(cweight)
					cweight=float(cweight)
				else:
					cname=c
					cweight=1.0
				self.constraints.append(Constraint(i,cname,None,cweight))
		else:
			if os.path.exists(constraints):
				constraintFiles = os.listdir(constraints)
				for i in range(len(constraintFiles)):
					constraintFile = constraintFiles[i]
					if constraintFile[-3:] == ".py":
						self.constraints.append(Constraint(i,os.path.join(constraints, constraintFile[:-3]),None,1))

	def maxS(self):
		return self.posLimit[0]
		
	def maxW(self):
		return self.posLimit[1]
	
	


	def genWordMatrix(self,wordlist):
		import prosodic
		if prosodic.config['resolve_optionality']:
			return list(product(*wordlist))	# [ [on, the1, ..], [on, the2, etc]
		else:
			return [ [ w[0] for w in wordlist ] ]
	
	def genSlotMatrix(self,words):
		matrix=[]
		
		for row in self.genWordMatrix(words):
			unitlist = []
			id=-1
			wordnum=-1
			for word in row:
				wordnum+=1
				syllnum=-1
				for unit in word.children:	# units = syllables
					syllnum+=1
					id+=1
					wordpos=(syllnum+1,len(word.children))
					unitlist.append(Slot(id, unit, word.sylls_text[syllnum], wordpos, word, i_word=wordnum, i_syll_in_word=syllnum))
					
			if not self.splitheavies:
				matrix.append(unitlist)
			else:
				unitlist2=[]
				for slot in unitlist:
					if bool(slot.feature('prom.weight')):
						slot1=Slot(slot.i,slot.children[0],slot.token,slot.wordpos,slot.word)
						slot2=Slot(slot.i,slot.children[0],slot.token,slot.wordpos,slot.word)
						
						## mark as split
						slot1.issplit=True
						slot2.issplit=True
						
						## demote
						slot2.feats['prom.stress']=0.0
						slot1.feats['prom.weight']=0.0
						slot2.feats['prom.weight']=0.0
						
						## split token
						slot1.token= slot1.token[ : len(slot1.token)/2 ]
						slot2.token= slot2.token[len(slot1.token)/2 + 1 : ]
						
						unitlist2.append([slot,[slot1,slot2]])
					else:
						unitlist2.append([slot])
				
				#unitlist=[]
				for row in list(product(*unitlist2)):
					unitlist=[]
					for x in row:
						if type(x)==type([]):
							for y in x:
								unitlist.append(y)
						else:
							unitlist.append(x)
					matrix.append(unitlist)
			
			
				
		# for r in matrix:
		# 	for y in r:
		# 		print y
		# 	print
		# 	print	
		
		return matrix
		
		
	
	def parse(self,wordlist,numSyll=0,numTopBounded=10):
		numTopBounded = self.config.get('num_bounded_parses_to_store',numTopBounded)
		#print '>> NTB!',numTopBounded
		from Parse import Parse
		if not numSyll:
			return []
		
		
		slotMatrix = self.genSlotMatrix(wordlist)
		if not slotMatrix: return None

		constraints = self.constraints

		
		allParses = []
		allBoundedParses=[]
		for slots in slotMatrix:
			_parses,_boundedParses = self.parseLine(slots)
			allParses.append(_parses)
			allBoundedParses+=_boundedParses
		
		parses,_boundedParses = self.boundParses(allParses)

		parses.sort()		

		allBoundedParses+=_boundedParses

		allBoundedParses.sort(key=lambda _p: (-_p.numSlots, _p.score()))
		allBoundedParses=allBoundedParses[:numTopBounded]
		#allBoundedParses=[]
		
		"""print parses
		print
		print allBoundedParses
		for parse in allBoundedParses:
			print parse.__report__()
			print
			print parse.boundedBy if type(parse.boundedBy) in [str,unicode] else parse.boundedBy.__report__()
			print
			print
			print
		"""

		return parses,allBoundedParses
		
	def boundParses(self, parseLists):
		unboundedParses = []
		boundedParses=[]
		for listIndex in range(len(parseLists)):
			for parse in parseLists[listIndex]:
				for parseList in parseLists[listIndex+1:]:
					for compParse in parseList:
						if compParse.isBounded:
							continue
						relation = parse.boundingRelation(compParse)
						if relation == Bounding.bounded:
							parse.isBounded = True
							parse.boundedBy = compParse
						elif relation == Bounding.bounds:
							compParse.isBounded = True
							compParse.boundedBy = parse
							
		for parseList in parseLists:
			for parse in parseList:
				if not parse.isBounded:
					unboundedParses.append(parse)
				else:
					boundedParses.append(parse)
					
		return unboundedParses,boundedParses
		
	def parseLine(self, slots):
	
		numSlots = len(slots)
			
		initialParse = Parse(self, numSlots)
		parses = initialParse.extend(slots[0])
		parses[0].comparisonNums.add(1)

		boundedParses=[]
		
		
		for slotN in range(1, numSlots):
		
			newParses = []
			for parse in parses:
				newParses.append(parse.extend(slots[slotN]))
				
			for parseSetIndex in range(len(newParses)):
			
				parseSet = newParses[parseSetIndex]
				
				for parseIndex in range(len(parseSet)):
				
					parse = parseSet[parseIndex]
					parse.comparisonParses = []
					
					if len(parseSet) > 1 and parseIndex == 0:
						parse.comparisonNums.add(parseSetIndex)
					
					for comparisonIndex in parse.comparisonNums:
					
						# should be a label break, but not supported in Python
						# find better solution; redundant checking
						if parse.isBounded:
							break

						try:
							for comparisonParse in newParses[comparisonIndex]:
							
								if parse is comparisonParse:
									continue
							
								if not comparisonParse.isBounded:
								
									if parse.canCompare(comparisonParse):
									
										boundingRelation = parse.boundingRelation(comparisonParse)
										
										if boundingRelation == Bounding.bounds:
											comparisonParse.isBounded = True
											comparisonParse.boundedBy = parse
											
										elif boundingRelation == Bounding.bounded:
											parse.isBounded = True
											parse.boundedBy = comparisonParse
											break
											
										elif boundingRelation == Bounding.equal:
											parse.comparisonParses.append(comparisonParse)
										
									else:
										parse.comparisonParses.append(comparisonParse)
						except IndexError:
							pass
									
			parses = []
			#boundedParses=[]
			parseNum = 0
								
			for parseSet in newParses:
				for parse in parseSet:
					if parse.isBounded:
						boundedParses+=[parse]
					elif parse.score() >= 1000:
						parse.unmetrical = True
						boundedParses+=[parse]
					else:
						parse.parseNum = parseNum
						parseNum += 1
						parses.append(parse)

			
			for parse in parses:
			
				parse.comparisonNums = set()
				
				for compParse in parse.comparisonParses:
					if not compParse.isBounded:
						parse.comparisonNums.add(compParse.parseNum)
		


		return parses,boundedParses
	
	def printParses(self,parselist,lim=False):		# onlyBounded=True, [option done through "report" now]
		n = len(parselist)
		l_i = list(reversed(range(n)))
		#parselist.reverse()
		o=""
		for i,parse in enumerate(reversed(parselist)):
			#if onlyBounded and parse.isBounded:
			#	continue
			
			o+='-'*20+'\n'
			o+="[parse #" + str(l_i[i]+1) + " of " + str(n) + "]: " + str(parse.getErrorCount()) + " errors"

			if parse.isBounded:
				o+='\n[**** Harmonically bounded ****]\n'+str(parse.boundedBy)+' --[bounds]-->'
			elif parse.unmetrical:
				o+='\n[**** Unmetrical ****]'
			o+='\n'+str(parse)+'\n'
			o+=parse.str_meter()+'\n'

			o+=parse.__report__(proms=False)+"\n"
			o+=self.printScores(parse.constraintScores)
			o+='-'*20
			o+="\n\n"
			i-=1
		return o
			
	def printScores(self, scores):
		output = "\n"
		for key, value in sorted(((str(k.name),v) for (k,v) in scores.items())):
			if not value: continue
			#output += makeminlength("[*"+key+"]:"+str(value),24)
			#output+='[*'+key+']: '+str(value)+"\n"
			output+='[*'+key+']: '+str(value)+"  "
		#output = output[:-1]
		if not output.strip(): output=''
		output +='\n'
		return output
		

def parse_ent(ent,meter,init):
	#print init, type(init), dir(init)
	ent.parse(meter,init=init)
	init._Text__parses[meter].append( ent.allParses(meter) )
	init._Text__bestparses[meter].append( ent.bestParse(meter) )
	init._Text__parsed_ents[meter].append(ent)
	ent.scansion(meter=meter,conscious=True)