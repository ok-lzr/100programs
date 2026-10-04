def input_info():
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
    
    return celsius, unit

def CtoF(celsius):
    target = celsius * 9 / 5 + 32
    print(f"{celsius:.2f}℃ = {target:.2f}℉")

def CtoK(celsius):
    target = celsius + 273.15
    print(f"{celsius:.2f}℃ = {target:.2f}K")

def main():
    exit = ""
    while exit != "q":
        celsius, unit = input_info()
        if unit == "F":
            CtoF(celsius)
        elif unit == "K":
            CtoK(celsius)
        exit = input("退出请输入q：")

main()