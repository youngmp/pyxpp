import ctypes as ct
import os
import numpy as np

# load xpp api compiled with libX11.so
xppa = ct.cdll.LoadLibrary('../xpp_source/libxppAPI.so')

# figure out how to initialize input array in python to pass into c
arr = (ct.c_char_p*3)()
home = os.path.expanduser("~")
arr[0] = (home+'/Dropbox/xpp-py/xpp_source/xppaut').encode('utf-8')
arr[1] = (home+'/Dropbox/xpp-py/xpp_source/ode/lecar.ode').encode('utf-8')
arr[2] = '-silent'.encode('utf-8')

xppa.do_main_py(3,arr)
xppa.integrate_once_py.argtypes = np.ctypeslib.ndpointer(dtype=ct.c_float,ndim=1),
xppa.integrate_once_py.restype = None

xppa.get_ic.argtypes = [ct.c_int,np.ctypeslib.ndpointer(dtype=ct.c_float,ndim=1)]

# run sim
init_c = np.array([.01,-1],dtype=ct.c_float)
print('init_c type',type(init_c))
xppa.integrate_once_py(init_c)

# get data from xpp
maxrow = xppa.get_maxrow_browser()
maxcol = xppa.get_maxcol_browser()

data_all = np.zeros((maxrow,maxcol))
for i in range(maxcol):
    col_dat_addr = xppa.get_data_col(i)
    data_all[:,i] = list(ct.cast(col_dat_addr,ct.POINTER(ct.c_float*maxrow)).contents)

last = data_all[-1,1:]
last = last.astype(np.float32)

xppa.integrate_once_py(last)
#last_c = last.ctypes.data_as(ct.POINTER(ct.c_float))
print('last point to put into auto',last)
#print(type(last_c))

#xppa.get_ic(1,last)

    
xppa.auto_run_py()
