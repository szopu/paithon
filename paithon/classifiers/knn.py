import math

from datamining import vectors
from datamining.classifiers.core import BinaryClassifier, ClassifierParams
from datamining.data import DecisionalTable

DISTANCE_EUCLIDEAN_SQ = lambda x1, x2: sum([(e1 - e2) ** 2 for e1, e2 in zip(x1, x2)])
DISTANCE_EUCLIDEAN = lambda x1, x2: math.sqrt(sum([(e1 - e2) ** 2 for e1, e2 in zip(x1, x2)]))
DISTANCE_CHEBYSHEV = lambda x1, x2: max([abs(e1 - e2) for e1, e2 in zip(x1, x2)])
DISTANCE_MANHATTAN = lambda x1, x2: sum([abs(e1 - e2) for e1, e2 in zip(x1, x2)])


def DISTANCE_ONE_MINUS_PEARLSON(x1, x2):
    #n = len(x1)
    sum1 = sum(x1)
    sum2 = sum(x2)
    sum_sq1 = sum(vectors.coord_sq(x1))
    sum_sq2 = sum(vectors.coord_sq(x2))
    var1 = sum_sq1 - sum1 ** 2
    var2 = sum_sq2 - sum2 ** 2
    dot_product = sum(vectors.coord_mul(x1, x2))

    num = dot_product - (sum1 * sum2)
    den = math.sqrt(var1 * var2)
    return (1 - num / den) / 2.0

WEIGHT_UNIFORM = lambda dist: 1.0
WEIGHT_INVERTED = lambda dist: 1.0 / (1.0 + dist)
WEIGHT_EXPONENTIAL = lambda dist: math.exp(-dist)
WEIGHT_EXPONENTIAL_SQRT = lambda dist: math.exp(-math.sqrt(dist))
WEIGHT_INVERTED_SQRT = lambda dist: 1.0 / (1.0 + math.sqrt(dist))
WEIGHT_ONE_MINUS = lambda dist: 1.0 - dist  # only for distances in range [0,1]


class BinaryKNNClassifier(BinaryClassifier):
    def init(self, k=1, distance=DISTANCE_EUCLIDEAN_SQ, weight=WEIGHT_UNIFORM):
        self.table = DecisionalTable()
        self.distance = distance
        self.weight = weight
        self.k = k
        self.cache_enabled = False
        self.record_dist_ranking_cache = {}
        self.distance_fun_cache = {}

    def get_params(self):
        return ClassifierParams(k=self.k,
                                distance=self.distance,
                                weight=self.weight)

    def set_params(self, params):
        self.distance = params.get('distance', self.distance)
        self.weight = params.get('weight', self.weight)
        self.k = params.get('k', self.k)

    def set_cache(self, cache_enabled):
        self.cache_enabled = cache_enabled

    def train(self, table, decision_index=0, progressor=None):
        self.table = table
        self.decision_index = 0
        self.record_dist_ranking_cache = {}

    def old_record_distance_ranking(self, record, header):
        x1, y1 = record
        ranking = sorted([(self.distance(x1, rec[0]), rec) for rec in self.table],
                        key=lambda el: el[0])
        ranking = ranking[0:self.k]
        print [(dist, rec[1]) for dist, rec in ranking]
        return ranking

    def record_distance_ranking(self, record, header):
        if self.cache_enabled:
            if record in self.record_dist_ranking_cache:
                ranking = self.record_dist_ranking_cache[record]
                if (len(ranking) >= self.k
                        and self.distance_fun_cache[record] == self.distance):
                    return ranking[0:self.k]

        x1, y1 = record
        d = lambda rec: self.distance(x1, rec[0])
        table_iter = iter(self.table)
        ranking = []
        for __, rec in zip(range(self.k), table_iter):
            ranking.append((d(rec), rec))

        ranking.sort(key=lambda el: el[0])

        dist_threshold = ranking[-1][0]
        for rec in table_iter:
            rec_dist = d(rec)
            if rec_dist < dist_threshold:
                ranking.append((rec_dist, rec))
                ranking.sort(key=lambda el: el[0])
                ranking.pop()
                dist_threshold = ranking[-1][0]

        if self.cache_enabled:
            self.record_dist_ranking_cache[record] = ranking
            self.distance_fun_cache[record] = self.distance

        return ranking

    def rank_record(self, record, header):
        x1, y1 = record
        w = self.weight
        r = lambda rec: 1.0 if rec[1][self.decision_index] == self.positive_decision else 0.0
        record_distance_ranking = self.record_distance_ranking(record, header)
        ranking = [(w(dist), r(rec))
                    for dist, rec in record_distance_ranking]
        weight_sum = sum([weight for weight, __ in ranking])

        #return ranking[0][1]
        return sum([weight * rank for weight, rank in ranking]) / weight_sum

    def full_rankings(self, table, params_list):
        start_params = self.get_params()
        for params in params_list:
            #NO DISTANCE FUNCITION CHANGE!!!
            assert ('distance' not in params)
            self.set_params(params)
            yield self.full_ranking(table)
        self.set_params(start_params)
