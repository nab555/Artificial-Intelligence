'''
Question 1
Let's imagine a situation you went to the market and filled your baskets (basket1 and basket2) with fruits. 
You wanted to have one of each kind but realized that some fruits were put in both baskets. 
Task 1. Your first task is to remove everything from basket2 that is already present in basket1. 
Task 2. After the removal it is reasonable to anticipate that one of the baskets might weigh more compared to the another (all fruit kinds weight the same). 
Therefore, the second task is to transfer some fruits from a heavier basket to the lighter one to get approximately the same weightamount of fruits.'''


basket1 = ["apple", "banana", "cherry", "grape", "mango"]
basket2 = ["banana", "kiwi", "orange", "mango", "pear"]

for item in basket1:
 if item in basket2:
  basket2.remove(item);

print(basket1);
print(basket2);

while len(basket2) < len(basket1):
 fruit = basket1.pop()
 basket2.append(fruit)

print(basket1);
print(basket2);

