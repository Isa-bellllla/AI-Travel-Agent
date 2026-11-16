"""Hybrid ranking. Cached neural embeddings optional; local LSA baseline always available."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

class HybridIndex:
    def __init__(self,db,provider=None,cache_dir=None):
        self.db=db; self.ids=list(db.records); self.provider=provider
        docs=[db.document(db.records[i]) for i in self.ids]
        self.vectorizer=TfidfVectorizer(ngram_range=(1,2),strip_accents='unicode',sublinear_tf=True)
        self.sparse=self.vectorizer.fit_transform(docs)
        self.svd=TruncatedSVD(n_components=min(96,len(docs)-1,self.sparse.shape[1]-1),random_state=7)
        self.latent=normalize(self.svd.fit_transform(self.sparse))
        self.model=os.getenv('EMBEDDING_MODEL','').strip()
        self.neural=None; self.mode='TF-IDF + local latent semantic analysis (no pretrained model)'
        if self.model:
            if provider is None or not hasattr(provider,'embed'): raise ValueError('Embedding provider missing')
            cache=Path(cache_dir or Path(__file__).resolve().parents[1]/'.cache')
            cache.mkdir(parents=True,exist_ok=True)
            fingerprint=hashlib.sha256((db.digest+'|'+self.model+'|'+str(getattr(provider,'base',''))+'|v1').encode()).hexdigest()
            path=cache/(fingerprint+'.npy')
            if path.exists(): vectors=np.load(path,allow_pickle=False)
            else:
                vectors=np.array([v for start in range(0,len(docs),32) for v in provider.embed(docs[start:start+32],self.model)])
                if len(vectors)!=len(docs): raise ValueError('Embedding count mismatch')
                np.save(path,vectors,allow_pickle=False)
            if vectors.ndim!=2 or len(vectors)!=len(docs) or not np.isfinite(vectors).all(): raise ValueError('Invalid embedding cache')
            self.neural=normalize(vectors); self.mode='Ollama neural embeddings + TF-IDF'
        self.positions={i:n for n,i in enumerate(self.ids)}

    def rank(self,query,candidates,preferences=(),budget=None,month=None,similar_id=None):
        if not candidates: return []
        text=query or ' '.join(p.value for p in preferences if not p.negated)
        if similar_id:
            text += ' '+self.db.document(self.db.records[similar_id])
        sparse=self.vectorizer.transform([text])
        lexical=(self.sparse@sparse.T).toarray().ravel()
        if self.neural is not None:
            vector=normalize(np.array(self.provider.embed([text],self.model)))
            semantic=(self.neural@vector.T).ravel()
        else:
            semantic=(self.latent@normalize(self.svd.transform(sparse)).T).ravel()
        scores={}
        for r in candidates:
            n=self.positions[r['id']]
            label_overlap=0
            # A ranking signal only; never evidence for hard semantic constraints.
            for p in preferences:
                weight=p.priority/5
                field=p.target_field or 'labels'
                query_value=p.normalized_value or p.value
                overlap=len(set(query_value.lower().split()) & set(str(r[field]).lower().split()))
                label_overlap += (-1 if p.negated else 1)*weight*min(overlap,3)/3
            price,_=self.db.price(r,month)
            budget_fit=0.1*(1-min(price/budget,2)) if budget else 0
            scores[r['id']]=float(.45*lexical[n]+.45*semantic[n]+.1*label_overlap+budget_fit)
        return sorted(candidates,key=lambda r:(-scores[r['id']],r['id']))
