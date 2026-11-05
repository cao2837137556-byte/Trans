"""Read-only row indirection; indexing a minibatch allocates only that minibatch."""
import numpy as np


class IndexedMatrix:
    def __init__(self,base,indices,columns=None):
        if isinstance(base,IndexedMatrix):
            if columns is not None:raise ValueError('NESTED_COLUMN_SELECTION')
            indices=base.indices[_indices(indices,len(base))]
            columns=base.columns;base=base.base
        else:
            base=np.asarray(base)
            if base.ndim!=2:raise ValueError('MATRIX_REQUIRED')
            indices=_indices(indices,len(base))
        self.base=base;self.indices=np.array(indices,dtype=np.int64,copy=True)
        self.indices.flags.writeable=False
        self.columns=slice(None) if columns is None else columns
        if not isinstance(self.columns,slice):raise ValueError('COLUMN_SLICE_REQUIRED')
        self.shape=(len(self.indices),len(range(*self.columns.indices(base.shape[1]))))
        self.dtype=base.dtype;self.ndim=2;self.peak_read_rows=0;self.read_calls=0

    def __len__(self):return self.shape[0]

    def __array__(self,dtype=None,copy=None):
        raise TypeError('EXPLICIT_BATCH_REQUIRED: do not materialize indexed feature pools')

    def __getitem__(self,selection):
        if isinstance(selection,tuple):raise TypeError('USE_ROW_BATCH_THEN_COLUMNS')
        ix=self.indices[selection]
        size=1 if np.ndim(ix)==0 else len(ix)
        self.read_calls+=1;self.peak_read_rows=max(self.peak_read_rows,size)
        result=self.base[ix,self.columns]
        result.flags.writeable=False
        return result


def _indices(indices,size):
    ix=np.asarray(indices)
    if ix.ndim==1 and ix.size==0:return np.empty(0,dtype=np.int64)
    if ix.ndim!=1 or ix.dtype.kind not in 'iu':raise ValueError('INTEGER_ROW_INDICES_REQUIRED')
    if np.any(ix < -size) or np.any(ix >= size):raise IndexError('ROW_INDEX_OUT_OF_RANGE')
    return ix.astype(np.int64,copy=False)


def matrix(value):
    return value if isinstance(value,IndexedMatrix) else np.asarray(value)


def take(value,indices,columns=None):
    return IndexedMatrix(value,indices,columns)


def hash_matrix(digest,value,block_rows=1024):
    if type(block_rows) is not int or block_rows<1:raise ValueError('POSITIVE_BLOCK_ROWS_REQUIRED')
    arr=matrix(value)
    digest.update(str(arr.dtype).encode());digest.update(str(arr.shape).encode())
    for start in range(0,len(arr),block_rows):digest.update(arr[start:start+block_rows].tobytes(order='C'))
