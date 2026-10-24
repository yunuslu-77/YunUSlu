### Example: a precise edit
read output:
```
    12	def total(items):
    13	    return sum(i.price for i in items)
```
Correct edit: find = `    return sum(i.price for i in items)` (4 spaces, no "13", no tab) →
replace = `    return sum(i.price * i.qty for i in items)`
