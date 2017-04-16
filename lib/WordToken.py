from entity import entity,being


class WordToken(entity):
    def __init__(self,words,token,is_punct=False,sentence=None):
        self.children=words
        self.token=token
        self.is_punct=is_punct
        self.sentence=None

    def __getitem__(self,key):
        return self.children[key]

    def __repr__(self):
		return "<"+self.classname()+":"+self.u2s(self.token)+">"