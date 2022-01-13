#! /usr/bin/env python3
import random


def getperm(l):
    seed = sum([ord(a) for a in l])
    random.seed(seed)
    perm = list(range(len(l)))
    random.shuffle(perm)
    random.seed()  # optional, in order to not impact other code based on random
    return perm


def shuffle(l):
    perm = getperm(l)
    j = [l[j] for j in perm]
    return "".join(j)


def unshuffle(l):
    perm = getperm(l)
    res = [None] * len(l)
    for i, j in enumerate(perm):
        res[j] = l[i]
    j = res
    return "".join(j)


class PseudoInt:
    alphabet = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"

    def __init__(self, seed):
        random.seed(seed)
        alphabet = [c for c in self.alphabet]
        random.shuffle(alphabet)
        self.alphabet = "".join(alphabet)
        self.offset = random.randint(40, 2048)
        self.gap = random.randint(40, 2048)
        random.seed()

    def encode(self, x):
        x *= self.gap
        x += self.offset
        digs = [c for c in self.alphabet]
        digs = "".join(digs)
        digits = []
        base = len(self.alphabet)
        while x:
            digits.append(digs[int(x % base)])
            x = int(x / base)
        digits = shuffle("".join(digits))
        digits = [c for c in digits]
        return "".join(digits)

    def decode(self, s):
        digits = [c for c in s]
        digits = unshuffle("".join(digits))

        base = len(self.alphabet)
        x = 0
        for d in digits[::-1]:
            x = x * base + self.alphabet.index(d)
        return (x - self.offset) / self.gap


if __name__ == "__main__":
    p = PseudoInt("test")
    for i in range(100000000000, 100000000100):
        assert i == p.decode(p.encode(i))
        print(p.encode(i))
