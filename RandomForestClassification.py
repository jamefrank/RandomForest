# -*- encoding: utf-8 -*-
#@File    :   RandomForestClassification.py
#@Time    :   2024/01/24 14:57:38
#@Author  :   frank 
#@Email:
#@Description:




import pandas as pd
import numpy as np
import random
import math
import collections
from joblib import Parallel, delayed


class Tree(object):
    """定义一棵决策树"""
    def __init__(self):
        self.split_feature = None
        self.split_value = None
        self.leaf_value = None
        self.tree_left = None
        self.tree_right = None

    def calc_predict_value(self, dataset):
        """通过递归决策树找到样本所属叶子节点"""
        if self.leaf_value is not None:
            return self.leaf_value
        elif dataset[self.split_feature] <= self.split_value:
            return self.tree_left.calc_predict_value(dataset)
        else:
            return self.tree_right.calc_predict_value(dataset)

    def describe_tree(self):
        """以json形式打印决策树，方便查看树结构"""
        if not self.tree_left and not self.tree_right:
            leaf_info = "{leaf_value:" + str(self.leaf_value) + "}"
            return leaf_info
        left_info = self.tree_left.describe_tree()
        right_info = self.tree_right.describe_tree()
        tree_structure = "{split_feature:" + str(self.split_feature) + \
                         ",split_value:" + str(self.split_value) + \
                         ",left_tree:" + left_info + \
                         ",right_tree:" + right_info + "}"
        return tree_structure


class RandomForestClassifier(object):
    def __init__(self, n_estimators=10, max_depth=-1, min_samples_split=2, min_samples_leaf=1,
                 min_split_gain=0.0, colsample_bytree=None, subsample=0.8, random_state=None):
        """
        随机森林参数
        ----------
        n_estimators:      树数量
        max_depth:         树深度，-1表示不限制深度
        min_samples_split: 节点分裂所需的最小样本数量，小于该值节点终止分裂
        min_samples_leaf:  叶子节点最少样本数量，小于该值叶子被合并
        min_split_gain:    分裂所需的最小增益，小于该值节点终止分裂
        colsample_bytree:  列采样设置，可取[sqrt、log2]。sqrt表示随机选择sqrt(n_features)个特征，
                           log2表示随机选择log(n_features)个特征，设置为其他则不进行列采样
        subsample:         行采样比例
        random_state:      随机种子，设置之后每次生成的n_estimators个样本集不会变，确保实验可重复
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth if max_depth != -1 else float('inf')
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.min_split_gain = min_split_gain
        self.colsample_bytree = colsample_bytree
        self.subsample = subsample
        self.random_state = random_state
        self.trees = None
        self.feature_importances_ = dict()

    def fit(self, dataset, targets):
        """模型训练入口"""
        assert targets.unique().__len__() == 2, "There must be two class for targets!"
        
        # Series是一维数据结构，类似于带有标签索引的数组。DataFrame是二维数据结构，类似于电子表格或SQL表格，包含多个列
        targets = targets.to_frame(name='label')

        # 这段代码的目的是从0到self.n_estimators-1的范围中随机选择self.n_estimators个不重复的元素，
        # 并将结果存储在random_state_stages变量中。这样可以创建一个具有随机顺序的元素列表
        if self.random_state:
            random.seed(self.random_state)
        random_state_stages = random.sample(range(self.n_estimators), self.n_estimators)

        # 两种列采样方式
        if self.colsample_bytree == "sqrt":
            self.colsample_bytree = int(len(dataset.columns) ** 0.5)
        elif self.colsample_bytree == "log2":
            self.colsample_bytree = int(math.log(len(dataset.columns)))
        else:
            self.colsample_bytree = len(dataset.columns)

        # 并行建立多棵决策树
        # 使用joblib库中的Parallel类来创建并行计算的对象，
        # n_jobs=-1表示使用所有可用的处理器核心进行并行计算，
        # verbose=0表示不输出任何冗余信息，
        # backend="threading"指定使用线程作为并行计算的后端
        # joblib库是基于multiprocessing库的高级封装，提供了更简单和更高级的接口来实现并行计算
        self.trees = Parallel(n_jobs=1, verbose=0, backend="threading")(
            delayed(self._parallel_build_trees)(dataset, targets, random_state)
                for random_state in random_state_stages)
        
    def _parallel_build_trees(self, dataset, targets, random_state):
        """bootstrap有放回抽样生成训练样本集，建立决策树"""
        # 随机获取样本的colsample_bytree个属性
        subcol_index = random.sample(dataset.columns.tolist(), self.colsample_bytree)
        
        # 从DataFrame中进行抽样
        # n参数表示要抽取的样本数量:样本总量*下采样比例
        # replace=True表示允许有放回地抽样，即一个样本可以被抽取多次
        # random_state=random_state表示使用给定的随机种子进行抽样，从而保证在相同的随机种子下可以得到可重复的抽样结果
        dataset_stage = dataset.sample(n=int(self.subsample * len(dataset)), replace=True, 
                                        random_state=random_state).reset_index(drop=True)
        dataset_stage = dataset_stage.loc[:, subcol_index]
        
        # 同样对标签进行随机下采样，因为随机种子是确定的，所以可以保证上面的属性数据和下面的标签数据是对应起来的
        targets_stage = targets.sample(n=int(self.subsample * len(dataset)), replace=True, 
                                        random_state=random_state).reset_index(drop=True)
        
        # 根据属性和标签的下采样的样本数据创建决策树
        tree = self._build_single_tree(dataset_stage, targets_stage, depth=0)
        print(tree.describe_tree())
        return tree

    def _build_single_tree(self, dataset, targets, depth):
        """递归建立决策树"""
        # 如果该节点的类别全都一样/样本小于分裂所需最小样本数量，则选取出现次数最多的类别。终止分裂
        if len(targets['label'].unique()) <= 1 or dataset.__len__() <= self.min_samples_split:
            tree = Tree()
            tree.leaf_value = self.calc_leaf_value(targets['label'])
            return tree

        if depth < self.max_depth:
            best_split_feature, best_split_value, best_split_gain = self.choose_best_feature(dataset, targets)
            left_dataset, right_dataset, left_targets, right_targets = \
                self.split_dataset(dataset, targets, best_split_feature, best_split_value)

            tree = Tree()
            # 如果父节点分裂后，左叶子节点/右叶子节点样本小于设置的叶子节点最小样本数量，则该父节点终止分裂
            if left_dataset.__len__() <= self.min_samples_leaf or \
                    right_dataset.__len__() <= self.min_samples_leaf or \
                    best_split_gain <= self.min_split_gain:
                tree.leaf_value = self.calc_leaf_value(targets['label'])
                return tree
            else:
                # 如果分裂的时候用到该特征，则该特征的importance加1
                self.feature_importances_[best_split_feature] = \
                    self.feature_importances_.get(best_split_feature, 0) + 1

                tree.split_feature = best_split_feature
                tree.split_value = best_split_value
                tree.tree_left = self._build_single_tree(left_dataset, left_targets, depth+1)
                tree.tree_right = self._build_single_tree(right_dataset, right_targets, depth+1)
                return tree
        # 如果树的深度超过预设值，则终止分裂
        else:
            tree = Tree()
            tree.leaf_value = self.calc_leaf_value(targets['label'])
            return tree

    def choose_best_feature(self, dataset, targets):
        """寻找最好的数据集划分方式，找到最优分裂特征、分裂阈值、分裂增益"""
        best_split_gain = 1
        best_split_feature = None
        best_split_value = None

        for feature in dataset.columns:
            if dataset[feature].unique().__len__() <= 100:
                unique_values = sorted(dataset[feature].unique().tolist())
            # 如果该维度特征取值太多，则选择100个百分位值作为待选分裂阈值
            else:
                unique_values = np.unique([np.percentile(dataset[feature], x)
                                           for x in np.linspace(0, 100, 100)])

            # 对可能的分裂阈值求分裂增益，选取增益最大的阈值
            for split_value in unique_values:
                left_targets = targets[dataset[feature] <= split_value]
                right_targets = targets[dataset[feature] > split_value]
                
                # 基尼系数（Gini coefficient）是衡量分类模型不纯度的指标，用于评估模型的预测能力。
                # 基尼系数的取值范围为0到1，其中0表示最佳的纯度（所有样本属于同一类别），而1表示最差的纯度（样本在每个类别中均匀分布）
                split_gain = self.calc_gini(left_targets['label'], right_targets['label'])

                if split_gain < best_split_gain:
                    best_split_feature = feature
                    best_split_value = split_value
                    best_split_gain = split_gain
        return best_split_feature, best_split_value, best_split_gain

    @staticmethod
    def calc_leaf_value(targets):
        """选择样本中出现次数最多的类别作为叶子节点取值"""
        label_counts = collections.Counter(targets)
        major_label = max(zip(label_counts.values(), label_counts.keys()))
        return major_label[1]

    @staticmethod
    def calc_gini(left_targets, right_targets):
        """分类树采用基尼指数作为指标来选择最优分裂点"""
        split_gain = 0
        for targets in [left_targets, right_targets]:
            gini = 1
            # 统计每个类别有多少样本，然后计算gini
            label_counts = collections.Counter(targets)
            for key in label_counts:
                prob = label_counts[key] * 1.0 / len(targets)
                gini -= prob ** 2
            split_gain += len(targets) * 1.0 / (len(left_targets) + len(right_targets)) * gini
        return split_gain

    @staticmethod
    def split_dataset(dataset, targets, split_feature, split_value):
        """根据特征和阈值将样本划分成左右两份，左边小于等于阈值，右边大于阈值"""
        left_dataset = dataset[dataset[split_feature] <= split_value]
        left_targets = targets[dataset[split_feature] <= split_value]
        right_dataset = dataset[dataset[split_feature] > split_value]
        right_targets = targets[dataset[split_feature] > split_value]
        return left_dataset, right_dataset, left_targets, right_targets

    def predict(self, dataset):
        """输入样本，预测所属类别"""
        res = []
        for _, row in dataset.iterrows():
            pred_list = []
            # 统计每棵树的预测结果，选取出现次数最多的结果作为最终类别
            for tree in self.trees:
                pred_list.append(tree.calc_predict_value(row))

            pred_label_counts = collections.Counter(pred_list)
            pred_label = max(zip(pred_label_counts.values(), pred_label_counts.keys()))
            res.append(pred_label[1])
        return np.array(res)


if __name__ == '__main__':
    df = pd.read_csv("source/wine.txt")
    # 从数据框中选择'label'列值为1或2的行，并以随机顺序对这些行进行重新排序，并重置索引。结果是一个新的数据框，其中仅包含'label'列值为1或2的行，并且行的顺序是随机的，并且索引是重置过的。
    # frac=1表示保留全部样本，random_state=66是随机种子，用于确保每次运行代码时得到相同的随机结果
    # drop=True表示丢弃原来的索引列
    df = df[df['label'].isin([1, 2])].sample(frac=1, random_state=66).reset_index(drop=True)
    
    clf = RandomForestClassifier(n_estimators=5,
                                 max_depth=5,
                                 min_samples_split=6,
                                 min_samples_leaf=2,
                                 min_split_gain=0.0,
                                 colsample_bytree="sqrt",
                                 subsample=0.8,
                                 random_state=66)
    # 取总样本的70%作为训练集
    train_count = int(0.7 * len(df))
    feature_list = ["Alcohol", "Malic acid", "Ash", "Alcalinity of ash", "Magnesium", "Total phenols", 
                    "Flavanoids", "Nonflavanoid phenols", "Proanthocyanins", "Color intensity", "Hue", 
                    "OD280/OD315 of diluted wines", "Proline"]
    clf.fit(df.loc[:train_count, feature_list], df.loc[:train_count, 'label'])

    from sklearn import metrics
    print(metrics.accuracy_score(df.loc[:train_count, 'label'], clf.predict(df.loc[:train_count, feature_list])))
    print(metrics.accuracy_score(df.loc[train_count:, 'label'], clf.predict(df.loc[train_count:, feature_list])))
