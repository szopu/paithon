from abc import ABCMeta, abstractproperty, abstractmethod
from collections import Counter

from ..core.types import HashableSlice, sequence
from .base import Model


class DecisionTree(Model):
    def __init__(self, disortion_measure):
        self._root_node = None
        self._disortion_measure = disortion_measure

    def gain(self, all_dec_values, dec_values_split):
        gain = self._disortion_measure(all_dec_values)
        for dec_values in  dec_values_split:
            gain -= self._disortion_measure(dec_values)
        return gain

    def value_split_dict(self, cond_dec_records, cond_attribute_index):
        sp_dict = {}
        for pair in cond_dec_records:
            cond_record, _ = pair
            cond_value = cond_record[cond_attribute_index]
            sp_dict.setdefault(cond_value, []).append(pair)
        return sp_dict

    def cut_split_dict(self, cond_dec_records, cond_attribute_index,
                        cut_value):

        lt_records = []
        gte_records = []
        for pair in cond_dec_records:
            cond_record, _ = pair
            cond_value = cond_record[cond_attribute_index]
            if cond_value < cut_value:
                lt_records.append(pair)
            else:
                gte_records.append(pair)
        sp_dict = {
            HashableSlice(None, cut_value): lt_records,
            HashableSlice(cut_value, None): gte_records,
        }
        return sp_dict

    def iter_decisions(self, cond_dec_records):
        for cond_rec, dec_rec in cond_dec_records:
            yield dec_rec[0]

    def iter_conditional_values(self, cond_dec_records, index):
        for cond_record, _ in cond_dec_records:
            yield cond_record[index]

    def score(self, cond_dec_records, split_dict):
        all_dec_values = list(self.iter_decisions(cond_dec_records))
        dec_values_split = [self.iter_decisions(x) for x in split_dict.values()]
        score_fun = self.gain
        return score_fun(all_dec_values, dec_values_split)

    def find_best_split_dict(self, cond_dec_records, cond_attributes):

        assert(hasattr(cond_attributes, '__len__'))
        assert(filter(None, cond_attributes))

        def generate_splits():
            for i, cond_attr in enumerate(cond_attributes):
                if cond_attr is not None:
                    if cond_attr.discrete:
                        spd = self.value_split_dict(cond_dec_records, i)
                        score = self.score(cond_dec_records, spd)
                        yield (score, spd, i)
                    elif cond_attr.numeric:
                        cond_values = set(self.iter_conditional_values(
                                            cond_dec_records, i))
                        for cond_value in cond_values:
                            spd = self.cut_split_dict(cond_dec_records, i,
                                                        cond_value)
                            split = spd.values()
                            if split[0] and split[1]:
                                score = self.score(cond_dec_records, spd)
                                yield (score, spd, i)

        return max(generate_splits(), key=lambda x: x[0])[1:3]

    def build_node_recursive(self, cond_dec_records, cond_attributes,
                                depth=None):
        cond_dec_records = sequence(cond_dec_records)
        decisions_counter = Counter(self.iter_decisions(cond_dec_records))

        if depth is None:
            sub_depth = None
        else:
            sub_depth = depth - 1

        assert(decisions_counter)

        if (depth == 0 or len(decisions_counter) == 1
                or not filter(None, cond_attributes)):
            # all decisions are the same
            # or all attributes were used previously in decision making
            # or tree is too big - use majority voting
            node = LeafDecisionNode()
            node._decision = decisions_counter.most_common(1)[0][0]

        else:
            #find the best split
            (spd, i) = self.find_best_split_dict(cond_dec_records,
                                                    cond_attributes)
            if (len(spd) == 2 and isinstance(spd.keys()[0], HashableSlice)
                    and isinstance(spd.keys()[1], HashableSlice)):
                #cut split (<)
                slice1, slice2 = spd.keys()
                cut_value = None
                gte_split = None
                lt_split = None
                if slice1.start is not None:
                    cut_value = slice1.start
                    lt_split = spd[slice2]
                    gte_split = spd[slice1]
                else:
                    cut_value = slice1.stop
                    lt_split = spd[slice1]
                    gte_split = spd[slice2]

                node = InequalityDecisionNode()
                node._attribute_index = i
                node._cut_value = cut_value
                node._lt_node = self.build_node_recursive(lt_split,
                                                            cond_attributes,
                                                            sub_depth)
                node._gte_node = self.build_node_recursive(gte_split,
                                                            cond_attributes,
                                                            sub_depth)

            else:
                #value split (==)

                #disabling attribute to be selected in subtree
                cond_attributes_copy = cond_attributes[:]
                cond_attributes_copy[i] = None
                node = EqualityDecisionNode()
                node._attribute_index = i
                node._node_map = {}
                for value, value_split in spd.iteritems():
                    node._node_map[value] = self.build_node_recursive(
                                                        value_split,
                                                        cond_attributes_copy,
                                                        sub_depth)
        return node

    def build(self, cond_dec_records, cond_attributes, depth=None):
        self._root_node = self.build_node_recursive(cond_dec_records,
                                                    cond_attributes, depth)

    def decision(self, cond_record):
        return self._root_node.decision(cond_record)


class DecisionNode(object):

    __metaclass__ = ABCMeta

    @abstractproperty
    def children(self):
        pass

    @abstractmethod
    def decision(self, cond_record):
        pass


class TestDecisionNode(DecisionNode):

    def __init__(self):
        self._attribute_index = None


class EqualityDecisionNode(TestDecisionNode):

    def __init__(self):
        super(EqualityDecisionNode, self).__init__()
        self._node_map = {}

    @property
    def children(self):
        return self._node_map.values()

    def decision(self, cond_record):
        value = cond_record[self._attribute_index]
        return self._node_map[value].decision(cond_record)


class InequalityDecisionNode(TestDecisionNode):

    def __init__(self):
        super(InequalityDecisionNode, self).__init__()
        self._cut_value = None
        self._lt_node = None
        self._gte_node = None

    @property
    def children(self):
        result = []
        if self._lt_node:
            result.append(self._lt_node)
        if self._gte_node:
            result.append(self._gte_node)
        return result

    def decision(self, cond_record):
        value = cond_record[self._attribute_index]
        node = self._lt_node if value < self._cut_value else self._gte_node
        return node.decision(cond_record)


class LeafDecisionNode(DecisionNode):

    def __init__(self):
        super(LeafDecisionNode, self).__init__()
        self._decision = None

    @property
    def children(self):
        return []

    def decision(self, cond_record):
        return self._decision
