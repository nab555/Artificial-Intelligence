'''
Operations on sets Using mathematical notation, 
we can define the following operations given two sets and : - 
the intersection between and (all elements which are in both and ) - 
the union between and (all elements which are either in or ) - 
the difference between and (all elements which are in but not in ) 
You are given 5 sets of integers A, B, C, D,E (You should see them in the console). 
What is the result of the following expression? 
(A union (B Intersection C)-(D Intersection E))
'''

A = {1, 2, 3, 4, 5, 6, 7}
B = {5, 7, 9, 11, 13, 15}
C = {1, 2, 8, 10, 11, 12, 13, 14, 15, 16, 17}
D = {1, 3, 5, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}
E = {9, 10, 11, 12, 13, 14, 15}

b_int_c = B.intersection(C);
print("B Intersection C: ", b_int_c);

aUnion_bIntersction_c = A.union(b_int_c);
print("A union (B Intersection C): ", aUnion_bIntersction_c);

d_int_e = D.intersection(E);
print("D Intersection E: ", d_int_e);

Final_diff = aUnion_bIntersction_c.difference(d_int_e);
print("Final Answer: ",Final_diff);

# Given sets (as lists to avoid using set functions)
A = [1, 2, 3, 4, 5, 6, 7]
B = [5, 7, 9, 11, 13, 15]
C = [1, 2, 8, 10, 11, 12, 13, 14, 15, 16, 17]
D = [1, 3, 5, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
E = [9, 10, 11, 12, 13, 14, 15]

# Step 1: B ∩ C  (intersection)
b_inter_c = []
for item in B:
    if item in C and item not in b_inter_c:
        b_inter_c.append(item)
print("B ∩ C =", b_inter_c)

# Step 2: A ∪ (B ∩ C)  (union)
a_union_b_inter_c = A.copy()
for item in b_inter_c:
    if item not in a_union_b_inter_c:
        a_union_b_inter_c.append(item)
print("A ∪ (B ∩ C) =", a_union_b_inter_c)

# Step 3: D ∩ E
d_inter_e = []
for item in D:
    if item in E and item not in d_inter_e:
        d_inter_e.append(item)
print("D ∩ E =", d_inter_e)

# Step 4: (A ∪ (B ∩ C)) − (D ∩ E)
result = []
for item in a_union_b_inter_c:
    if item not in d_inter_e:
        result.append(item)
print("Final Result =", result)

