while 1:
    try:
        celsius = float(input("请输入摄氏度℃（可输入小数，输出结果精确到两位小数）：\n"))
        break
    except ValueError:
        print("请输入数字！（不含符号）\n")
        
while 1:
    unit = input("请输入目标单位（可输入F（华氏度）、K（摄氏度））：\n")
    if unit != "F" and unit != "K":
        print("请输入支持的单位！")
    else:
        break

if unit == "F":
    target = celsius * 9 / 5 + 32
    print(f"{celsius:.2f}℃ = {target:.2f}℉")
elif unit == "K":
    target = celsius + 273.15
    print(f"{celsius:.2f}℃ = {target:.2f}K")

