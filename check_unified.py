# -*- coding: utf-8 -*-
import pandas as pd

for f in ["统一数据集_受试者主表.csv", "前测明细表.csv", "心率明细表.csv",
          "血液明细表_链接后.csv", "数据完整性矩阵.csv"]:
    try:
        df = pd.read_csv(r"D:\DEV\blood\统一数据集" + "\\" + f, encoding="utf-8-sig")
        print("=====", f, "shape:", df.shape)
        print(list(df.columns)[:45])
    except Exception as e:
        print("ERR", f, e)
