def calculate_gc_content(file_path):
    # Open the file in a with statement to ensure it gets closed properly
    with open(file_path, "r") as gene:
        print('Gene: ' + gene.name)

        # Skip the header line in gene sequence data
        gene.readline()

        # Dictionary to hold nucleotide counts
        nucleotides = {"g": 0, "c": 0, "a": 0, "t": 0}

        # Core program function
        for line in gene:
            line = line.lower()
            for char in line:
                # Increment the count of nucleotide if it's in the dictionary
                if char in nucleotides:
                    nucleotides[char] += 1

        total = sum(nucleotides.values())
        print(f'Total Base Pairs {total}')
        for base, count in nucleotides.items():
            print(f'{base.upper()} {count}')

        # Calculate GC content
        gc_content = (nucleotides['g'] + nucleotides['c']) / total
        return gc_content


print('###############################################################################')
print('Bioinformatics - Python program to calculate gc content (%) of genetic material')
print('###############################################################################')
print()

# List of file paths
gene_files = ["OCT4.txt", "SOX2.txt", "Klf2.txt", "c-Myc.txt"]

gc_contents = []
for file_path in gene_files:
    gc_content = calculate_gc_content(file_path)
    gc_contents.append(gc_content)
    print(f'GC Content: {round(gc_content * 100, 3)}%')
    print()

average_gc_content = sum(gc_contents) / len(gc_contents)
print(f'Average: {round(average_gc_content * 100, 3)}%')
print('###############################################################################')
