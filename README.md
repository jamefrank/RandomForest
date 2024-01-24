# RandomForest

随机森林，Random Forest（RF），分类和回归

# 环境配置

```shell
conda create -n sklearn python=3.8
conda activate sklearn
pip install -U scikit-learn
pip install pandas

```

# 数据

## wine

    这些特征主要用于描述葡萄酒样本的化学成分和特性。每个样本具有对应的类别标签，用于指示该样本属于哪个类别。在葡萄酒数据集中，通常有多个类别，例如红葡萄酒、白葡萄酒等。类别标签可以用于分类问题，即根据特征预测葡萄酒属于哪个类别。

* Alcohol：酒精含量
* Malic acid：苹果酸含量
* Ash：灰分含量
* Alcalinity of ash：灰分的碱度
* Magnesium：镁含量
* Total phenols：总酚含量
* Flavanoids：类黄酮含量
* Nonflavanoid phenols：非类黄酮酚类物质含量
* Proanthocyanins：原花青素含量
* Color intensity：颜色强度
* Hue：色调
* OD280/OD315 of diluted wines：稀释葡萄酒的吸光度比值
* Proline：脯氨酸含量
* label：葡萄酒样本的类别标签
