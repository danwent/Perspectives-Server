
import base64
import hashlib
from M2Crypto import BIO, RSA, EVP
import sys

if len(sys.argv) != 3: 
	print "usage: <notary-list-file> <private-key>" 
	exit(1) 


data = open(sys.argv[1],'r').read()
notary_priv_key= open(sys.argv[2],'r').read() 

m = hashlib.md5()
m.update(data)
bio = BIO.MemoryBuffer(notary_priv_key)
rsa_priv = RSA.load_key_bio(bio)
sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
sig = base64.standard_b64encode(sig_before_raw) 
print sig
