# Bioinformatics - Python program to calculate gc content (%) of genetic material
print('###############################################################################')
print('Bioinformatics - Python program to calculate gc content (%) of genetic material')
print('###############################################################################')
print()

# Skip the header line in gene sequence data
gene = open("OCT4.txt", "r")
print('Gene: ' + gene.name)
gene.readline()

#Set nucleotide values to 0
g=0;
c=0;
a=0;
t=0;

#Core program function  
for line in gene:
	line = line.lower()
	for char in line:
		if char == "g":
			g+=1
		if char == "c":
			c+=1
		if char == "a":
			a+=1
		if char == "t":
			t+=1
total = g+c+a+t	
print ('Total Base Pairs ' + str(total))			
print ('Guanine ' + str(g))
print ('Cytosine ' + str(c))
print ('Adenine ' + str(a))
print ('Thymine ' + str(t))

#Convert integer to a float for correct decimal format 
# 0. = convert to floating point
gc1 = (g+c) / (a+t+c+g)
print (str(round(gc1*100, 3)) + '%')
print()

# Skip the header line in gene sequence data
gene = open("SOX2.txt", "r")
print('Gene: ' + gene.name)
gene.readline()

#Set nucleotide values to 0
g=0;
c=0;
a=0;
t=0;

#Core program function  
for line in gene:
	line = line.lower()
	for char in line:
		if char == "g":
			g+=1
		if char == "c":
			c+=1
		if char == "a":
			a+=1
		if char == "t":
			t+=1
total = g+c+a+t	
print ('Total Base Pairs ' + str(g+c+a+t))			
print ('Guanine ' + str(g))
print ('Cytosine ' + str(c))
print ('Adenine ' + str(a))
print ('Thymine ' + str(t))

#Convert integer to a float for correct decimal format 
# 0. = convert to floating point
gc2 = (g+c) / (a+t+c+g)
print (str(round(gc2*100, 3)) + '%')
print()

# Skip the header line in gene sequence data
gene = open("Klf2.txt", "r")
print('Gene: ' + gene.name)
gene.readline()

#Set nucleotide values to 0
g=0;
c=0;
a=0;
t=0;

#Core program function  
for line in gene:
	line = line.lower()
	for char in line:
		if char == "g":
			g+=1
		if char == "c":
			c+=1
		if char == "a":
			a+=1
		if char == "t":
			t+=1
total = g+c+a+t			
print ('Total Base Pairs ' + str(total))				
print ('Guanine ' + str(g))
print ('Cytosine ' + str(c))
print ('Adenine ' + str(a))
print ('Thymine ' + str(t))

#Convert integer to a float for correct decimal format 
# 0. = convert to floating point
gc3 = (g+c) / (a+t+c+g)
print (str(round(gc3*100, 3)) + '%')
print()


# Skip the header line in gene sequence data
gene = open("c-Myc.txt", "r")
print('Gene: ' + gene.name)
gene.readline()

#Set nucleotide values to 0
g=0;
c=0;
a=0;
t=0;

#Core program function  
for line in gene:
	line = line.lower()
	for char in line:
		if char == "g":
			g+=1
		if char == "c":
			c+=1
		if char == "a":
			a+=1
		if char == "t":
			t+=1
total = g+c+a+t			
print ('Total Base Pairs ' + str(total))			
print ('Guanine ' + str(g))
print ('Cytosine ' + str(c))
print ('Adenine ' + str(a))
print ('Thymine ' + str(t))

#Convert integer to a float for correct decimal format 
# 0. = convert to floating point
gc4 = (g+c) / (a+t+c+g)
print (str(round(gc4*100, 3)) + '%')
print()

#Convert integer to a float for correct decimal format 
# 0. = convert to floating point
gc = (gc1+gc2+gc3+gc4) / 4
print ('Average: ' + str(round(gc*100, 3)) + '%')
print()
print('###############################################################################')

#Finish