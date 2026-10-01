while 1:
    try:
        celsius = float(input("请输入摄氏度℃（可输入小数，输出结果精确到两位小数）：\n"))
        break;
    except ValueError:
        print("请输入数字！（不含符号）\n")
fahrenheit = celsius * 9 / 5 + 32
print(f"{celsius:.2f}℃ = {fahrenheit:.2f}℉")
