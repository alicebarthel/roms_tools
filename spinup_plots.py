from netCDF4 import Dataset
from numpy import *
from matplotlib.pyplot import *
from calc_z import *

# Analyse a ROMS spinup by calculating and plotting 6 timeseries:
# Total heat content
# Total salt content
# Area-averaged ice shelf melt rate
# Total kinetic energy
# Maximum velocity
# Drake Passage transport


# Given the path to a ROMS grid file, calculate differentials for later
# integration.
# Input: grid_path = string containing path to ROMS grid file
# Output:
# dx_2d, dy_2d = differentials of x and y on the 2D rho-grid (lat x lon)
# dA = differential of area on the 2D rho-grid, masked with zice
# dV = differential of volume on the 3D rho-grid (depth x lat x lon)
def calc_grid (grid_path):

    # Grid parameters
    theta_s = 0.9
    theta_b = 4.0
    hc = 40
    N = 31
    # Radius of the Earth in m
    r = 6.371e6
    # Degrees to radians conversion factor
    deg2rad = pi/180.0

    # Read grid variables
    id = Dataset(grid_path, 'r')
    h = id.variables['h'][:,:]
    zice = id.variables['zice'][:,:]
    lon = id.variables['lon_rho'][:,:]
    lat = id.variables['lat_rho'][:,:]
    mask = id.variables['mask_rho'][:,:]
    id.close()

    # Mask lat and lon at land points
    lon = ma.masked_where(mask==0, lon)
    lat = ma.masked_where(mask==0, lat)
    # Save dimensions
    num_lat = size(lon, 0)
    num_lon = size(lon, 1)

    # Add or subtract 360 from longitude values which wrap around
    # so that longitude increases monotonically from west to east
    i = tile(arange(1, num_lon+1), (num_lat, 1))
    index1 = nonzero((i > 1200)*(lon < 100))
    lon[index1] = lon[index1] + 360
    index2 = nonzero((i < 200)*(lon > 300))
    lon[index2] = lon[index2] - 360

    # Interpolate to get longitude at the edges of each cell
    w_bdry = 0.5*(lon[:,0] + lon[:,-1] - 360)
    middle_lon = 0.5*(lon[:,0:-1] + lon[:,1:])
    e_bdry = 0.5*(lon[:,0] + 360 + lon[:,-1])
    lon_edges = ma.concatenate((w_bdry[:,None], middle_lon, e_bdry[:,None]), axis=1)
    # Subtract to get the change in longitude over each cell
    dlon = abs(lon_edges[:,1:] - lon_edges[:,0:-1])

    # Similarly for latitude
    s_bdry = lat[0,:]
    middle_lat = 0.5*(lat[0:-1,:] + lat[1:,:])
    n_bdry = lat[-1,:]*0 - 50
    lat_edges = ma.concatenate((s_bdry[None,:], middle_lat, n_bdry[None,:]))
    dlat = lat_edges[1:,:] - lat_edges[0:-1,:]

    # Convert from spherical to Cartesian coordinates
    # dy = r*dlat where dlat is converted to radians
    dy_2d = r*dlat*pi/180.0    
    # dx = r*cos(lat)*dlon where lat and dlon are converted to radians
    dx_2d = r*cos(pi*lat/180.0)*dlon*pi/180.0

    # Calculate dA and mask with zice
    dA = dx_2d*dy_2d
    id = Dataset(grid_path, 'r')
    mask = id.variables['mask_zice'][:,:]
    id.close()
    dA = ma.masked_where(mask==0, dA)

    # Copy dx and dy into 3D arrays, same at each depth level
    dy = tile(dy_2d, (N,1,1))
    dx = tile(dx_2d, (N,1,1))

    # Get a 3D array of z-coordinates; sc_r and Cs_r are unused in this script
    z, sc_r, Cs_r = calc_z(h, zice, lon, lat, theta_s, theta_b, hc, N)
    # We have z at the midpoint of each cell, now find it on the top and
    # bottom edges of each cell
    z_edges = zeros((size(z,0)+1, size(z,1), size(z,2)))
    z_edges[1:-1,:,:] = 0.5*(z[0:-1,:,:] + z[1:,:,:])
    # At surface, z = 0; at bottom, set z to be the same as the midpoint of
    # the deepest cell
    z_edges[0,:,:] = z[0,:,:]
    # Now find dz
    dz = z_edges[1:,:,:] - z_edges[0:-1,:,:]

    # Calculate dV
    dV = dx*dy*dz

    return dx[0,:,:], dy[0,:,:], dA, dV


# Read and return density.
# Input:
# rho_path = string containing path to density file
# t = timestep index in file_path
# Output: rho = density field at timestep t
def get_rho (rho_path, t):

    id = Dataset(rho_path, 'r')
    # Convert to float128 to prevent overflow later
    rho = ma.asarray(id.variables['rho'][t,:,:,:], dtype=float128)
    return rho


# Calculate ocean heat content at the given timestep t.
# Input:
# file_path = path to ocean history/averages file
# dV = elements of volume on the rho grid
# rho = density on the rho grid at timestep t
# t = timestep index in file_path
# Output: ohc = ocean heat content (J)
def calc_ohc (file_path, dV, rho, t):

    # Specific heat of polar seawater (J/K/kg)
    cp = 3974.0
    # Celsius to Kelvin conversion constant
    celsius2kelvin = 273.15

    # Read temperature, converting to float128 to prevent overflow during
    # integration
    id = Dataset(file_path, 'r')
    temp = ma.asarray(id.variables['temp'][t,:,:,:], dtype=float128)
    # Convert from Celsius to Kelvin
    temp = temp + celsius2kelvin
    id.close()

    # Integrate temp*rho*cp over volume to get OHC
    ohc = sum(temp*rho*cp*dV)
    return ohc


# Calculate total salt content at the given timestep t.
# Input:
# file_path = path to ocean history/averages file
# dV = elements of volume on the rho grid
# rho = density on the rho grid at timestep t
# t = timestep index in file_path
# Output: totalsalt = total salt content (kg)
def calc_totalsalt (file_path, dV, rho, t):

    # Read salinity, converting to float128 to prevent overflow during
    # integration
    id = Dataset(file_path, 'r')
    salt = ma.asarray(id.variables['salt'][t,:,:,:], dtype=float128)
    id.close()

    # Integrate 1e-3*salt*rho over volume to get total mass of salt
    totalsalt = sum(1e-3*salt*rho*dV)
    return totalsalt    


# Calculate area-averaged ice shelf melt rate at the given timestep t.
# Input:
# file_path = path to ocean history/averages file
# dA = elements of area on the rho grid, masked to only include ice shelves
# t = timestep index in file_path
# Output: avgismr = area-averaged ice shelf melt rate (m/y)
def calc_avgismr (file_path, dA, t):

    # Read ice shelf melt rate, converting to float128 to prevent overflow
    # during integration
    id = Dataset(file_path, 'r')
    ismr = ma.asarray(id.variables['m'][t,:,:], dtype=float128)
    # Convert from m/s to m/y
    ismr = ismr*365*24*60*60
    id.close()    

    # Integrate ismr over area and divide by total area to get average
    avgismr = sum(ismr*dA)/sum(dA)
    return avgismr


# Calculate total kinetic energy at the given timestep t.
# Input:
# file_path = path to ocean history/averages file
# dV = elements of volume on the rho grid
# rho = density on the rho grid at timestep t
# t = timestep index in file_path
# Output: tke = total kinetic energy (J)
def calc_tke (file_path, dV, rho, t):

    # Read u and v, converting to float 128 to prevent overflow during
    # integration
    id = Dataset(file_path, 'r')
    u = ma.asarray(id.variables['u'][t,:,:,:], dtype=float128)
    v = ma.asarray(id.variables['v'][t,:,:,:], dtype=float128)
    id.close()

    # Interpolate u onto the rho-grid
    w_bdry_u = 0.5*(u[:,:,0] + u[:,:,-1])
    middle_u = 0.5*(u[:,:,0:-1] + u[:,:,1:])
    e_bdry_u = w_bdry_u[:,:]
    u_rho = ma.concatenate((w_bdry_u[:,:,None], middle_u, e_bdry_u[:,:,None]), axis=2)

    # Interpolate v onto the rho-grid
    s_bdry_v = v[:,0,:]
    middle_v = 0.5*(v[:,0:-1,:] + v[:,1:,:])
    n_bdry_v = v[:,-1,:]
    v_rho = ma.concatenate((s_bdry_v[:,None,:], middle_v, n_bdry_v[:,None,:]), axis=1)

    # Integrate 0.5*rho*(u^2 + v^2) over volume to get TKE
    tke = sum(0.5*rho*(u_rho**2 + v_rho**2)*dV)
    return tke, u_rho, v_rho


# Calculate the maximum velocity.
# Input: u_rho, v_rho = u and v at timestep t, interpolated to the rho-grid
# Output: maxvel = maximum velocity (m/s)
def calc_maxvel (u_rho, v_rho):

    return amax(sqrt(u_rho**2 + v_rho**2))


# Calculate zonal transport through the Drake Passage.
# Input:
# file_path = path to ocean history/averages file
# dV = elements of volume on the rho grid
# dx_2d, dy_2d = elements of x and y on the 2D rho grid
# u_rho = u at timestep t, interpolated to the rho-grid
# Output: drakepsg_trans = zonal transport through the Drake Passage,
#                          integrated over depth and latitude, and averaged 
#                          between 65W and 55W
def calc_drakepsgtrans (file_path, dV, dx_2d, dy_2d, u_rho):

    # Bounds on Drake Passage
    lon_min = -65 + 360
    lon_max = -55 + 360

    # Read longitude on the rho grid
    id = Dataset(file_path, 'r')
    lon = id.variables['lon_rho'][:,:]
    id.close()

    # Only save the northernmost index of longitude
    lon = lon[-1,:]
    i = arange(1, size(lon)+1)

    # Find the first index where i is at least 1000 and lon exceeds lon_min
    i_min = nonzero((i >= 1000)*(lon >= lon_min))[0][0]
    # Same for lon_max
    i_max = nonzero((i >= 1000)*(lon >= lon_max))[0][0]
    # For each array, only save the slices between i_min and i_max
    dV_slice = dV[:,:,i_min:i_max]
    dx_2d_slice = dx_2d[:,i_min:i_max]
    dy_2d_slice = dy_2d[:,i_min:i_max]
    u_rho_slice = u_rho[:,:,i_min:i_max]

    # Since x varies with latitude, we can't just integrate dx at a single
    # latitude to get the distance x across the region. Instead, integrate
    # dx*dy over the region to get the area, then divide by the integral of
    # dy at a single longitude (since dy does not vary with longitude) to
    # get the y-averaged integral of dx.
    avg_int_dx = sum(dx_2d_slice*dy_2d_slice)/sum(dy_2d_slice[:,0])

    # Divide the integral of u_rho over volume by the y-averaged integral
    # of dx to get the x-averaged zonal transport between 65W and 55W.
    transport = sum(u_rho_slice*dV_slice)/avg_int_dx

    # Divide by 1e6 to convert to Sv and return the result.
    return transport*1e-6


# Command-line interface
if __name__ == "__main__":

    grid_path = raw_input('Enter path to grid file: ')
    file_path = raw_input('Enter path to ocean history/averages file: ')
    rho_path = raw_input('Enter path to density file: ')

    # Calculate differentials
    dx_2d, dy_2d, dA, dV = calc_grid(grid_path)
    # Read time data and convert from seconds to years
    id = Dataset(file_path, 'r')
    time = id.variables['ocean_time'][:]/(365*24*60*60)
    id.close()

    ohc = []
    totalsalt = []
    avgismr = []
    tke = []
    maxvel = []
    drakepsgtrans = []
    # Process each timestep separately to prevent memory overflow
    for t in range(size(time)):
        print 'Processing timestep '+str(t+1)+' of '+str(size(time))
        rho = get_rho(rho_path, t)
        print 'Calculating ocean heat content'
        ohc.append(calc_ohc(file_path, dV, rho, t))
        print 'Calculating total salt content'
        totalsalt.append(calc_totalsalt(file_path, dV, rho, t))
        print 'Calculating average ice shelf melt rate'
        avgismr.append(calc_avgismr(file_path, dA, t))
        print 'Calculating total kinetic energy'
        tke_tmp, u_rho, v_rho = calc_tke(file_path, dV, rho, t)
        tke.append(tke_tmp)
        print 'Calculating maximum velocity'
        maxvel.append(calc_maxvel(u_rho, v_rho))
        print 'Calculating Drake Passage transport'
        drakepsgtrans.append(calc_drakepsgtrans(file_path, dV, dx_2d, dy_2d, u_rho))

    # Plot each timeseries in sequence
    clf()
    plot(time, ohc)
    xlabel('Years')
    ylabel('Southern Ocean Heat Content (J)')
    show()
    plot(time, totalsalt)
    xlabel('Years')
    ylabel('Southern Ocean Salt Content (kg)')
    show()
    plot(time, avgismr)
    xlabel('Years')
    ylabel('Area-averaged Ice Shelf Melt Rate (m/y)')
    show()    
    plot(time, tke)
    xlabel('Years')
    ylabel('Southern Ocean Total Kinetic Energy (J)')
    show()
    plot(time, maxvel)
    xlabel('Years')
    ylabel('Maximum Southern Ocean Velocity (m/s)')
    show()
    plot(time, drakepsgtrans)
    xlabel('Years')
    ylabel('Drake Passage Transport (Sv)')
    show()
    