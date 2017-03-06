import netCDF4
import numpy as np

def set_to_val(nc,variable,icemask,val=0.0,n=-999):
    var    = nc.variables[variable]
    if n < 0:
        var[:] = val*icemask
    else:
        var[n,:] = val*icemask

# Make initialization of new cice-file...

in_file = '/short/m68/kaa561/metroms_iceshelf/data/cice_ini_orig.nc'
cicefile = '/short/m68/kaa561/metroms_iceshelf/data/cice_ini.nc'

NCAT = [0, 0.6445072, 1.391433, 2.470179, 4.567288, 1e+08] #upper limits of ice categories
varlist2d_null = ['uvel','vvel','scale_factor','swvdr','swvdf','swidr','swidf','strocnxT','strocnyT',
                  'stressp_1','stressp_2','stressp_3','stressp_4','stressm_1','stressm_2','stressm_3',
                  'stressm_4','stress12_1','stress12_2','stress12_3','stress12_4','iceumask','fsnow', 'accum_aice', 'accum_fresh', 'accum_fsalt', 'accum_fhocn', 'accum_fswthru', 'accum_strocnx', 'accum_strocny']
varlist3d_null = ['vsnon','iage','alvl','vlvl','apnd','hpnd','ipnd','dhs','ffrac','qsno001']

nc_in   = netCDF4.Dataset(in_file)
nc_cice   = netCDF4.Dataset(cicefile,'r+')

aice_r    = nc_in.variables['aice']   # mean ice concentration for grid cell
aicen_c   = nc_cice.variables['aicen']  # ice concentration per category in grid cell
vicen_c   = nc_cice.variables['vicen']  # volume per unit area of ice (in category n)
tsfcn_c = nc_cice.variables['Tsfcn']

mask_r    = nc_in.variables['mask']

hice_r    = nc_in.variables['hice']

icemask = np.where((aice_r[:]*mask_r[:]) > 0.1, 1, 0)
print icemask

for n in range(len(NCAT[1:])):
    print 'Upper limit: '+str(NCAT[n+1])
    aicen_c[n,:,:] = np.where(np.logical_and( hice_r[:,:] > NCAT[n], hice_r[:,:] < NCAT[n+1] ),
                              aice_r[:,:],0.0) * mask_r[:,:]
    vicen_c[n,:,:] = np.where(np.logical_and( hice_r[:,:] > NCAT[n], hice_r[:,:] < NCAT[n+1] ),
                              hice_r[:,:]*aice_r[:,:],0.0) * mask_r[:,:]
    # Make sure no negative values exist:
    aicen_c[n,:,:] = np.where(aicen_c[n,:,:] < 0.0, 0, aicen_c[n,:,:])
    vicen_c[n,:,:] = np.where(vicen_c[n,:,:] < 0.0, 0, vicen_c[n,:,:])
    tsfcn_c[n,:,:] = -20.15*icemask - 1.8*(1-icemask)
    
    for s in varlist3d_null:
        print s
        set_to_val(nc_cice,s,icemask,0.0,n)
    set_to_val(nc_cice,'sice001',icemask,0.0,n)
    set_to_val(nc_cice,'sice002',icemask,0.0,n)
    set_to_val(nc_cice,'sice003',icemask,0.0,n)
    set_to_val(nc_cice,'sice004',icemask,0.0,n)
    set_to_val(nc_cice,'sice005',icemask,0.0,n)
    set_to_val(nc_cice,'sice006',icemask,0.0,n)
    set_to_val(nc_cice,'sice007',icemask,0.0,n)
    set_to_val(nc_cice,'qice001',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice002',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice003',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice004',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice005',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice006',icemask,-2.0e8,n)
    set_to_val(nc_cice,'qice007',icemask,-2.0e8,n)
    set_to_val(nc_cice,'alvl',icemask,1.0,n)
    set_to_val(nc_cice,'vlvl',icemask,1.0,n)

for s in varlist2d_null:
    print s
    set_to_val(nc_cice,s,icemask,0.0)
    
nc_cice.istep1 = 0
nc_cice.time = 0
nc_cice.time_forc = 0
nc_cice.nyr = 1
nc_cice.month = 1
nc_cice.mday = 1
nc_cice.sec = 0


nc_cice.close()
print 'done'
