# importing matplotlib module
import matplotlib.pyplot as plt
import  matplotlib as mpl

# defining a list of x and v values
x_values = [1, 2, 3, 4, 5]
y_values = [x*x for x in x_values]

# plotting the graph
fig, ax = plt.subplots(figsize=(10, 6))

# check that the marker value is given as
# '$U0001F601$'

ax.plot(x_values, y_values, marker='$\U00000041$', ms=20)
ax.set_title('Squared Values', fontsize=15)
ax.set_xlabel('Value')
ax.set_ylabel('Square of Value')
plt.show()
