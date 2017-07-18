from netCDF4 import Dataset
from numpy import *
from numpy.ma import MaskedArray
from matplotlib.pyplot import *
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from matplotlib.cm import *
from matplotlib.colors import LinearSegmentedColormap
from rotate_vector_roms import *
from cartesian_grid_3d import *
from calc_z import *
from interp_lon_roms import *
# Import FESOM scripts (have to modify path first)
import sys
sys.path.insert(0, '/short/y99/kaa561/fesomtools')
from patches import *
from fesom_grid import *
from fesom_sidegrid import *
from unrotate_vector import *
from unrotate_grid import *

# File paths
roms_grid = '/short/m68/kaa561/metroms_iceshelf/apps/common/grid/circ30S_quarterdegree.nc'
roms_file = '/short/m68/kaa561/metroms_iceshelf/tmproms/run/intercomparison/2002_2016_avg.nc'
fesom_mesh_path_lr = '/short/y99/kaa561/FESOM/mesh/low_res/'
fesom_mesh_path_hr = '/short/y99/kaa561/FESOM/mesh/high_res/'
fesom_file_lr_o = '/short/y99/kaa561/FESOM/intercomparison_lowres/output/oce_2002_2016_avg.nc'
fesom_file_hr_o = '/short/y99/kaa561/FESOM/intercomparison_highres/output/oce_2002_2016_avg.nc'
fesom_file_lr_i = '/short/y99/kaa561/FESOM/intercomparison_lowres/output/wnet_2002_2016_avg.nc'
fesom_file_hr_i = '/short/y99/kaa561/FESOM/intercomparison_highres/output/wnet_2002_2016_avg.nc'
# Parameters for missing circle in ROMS grid
lon_c = 50
lat_c = -83
radius = 10.1
nbdry = -63+90
# Constants
deg2rad = pi/180.0
sec_per_year = 365.25*24*3600
# ROMS vertical grid parameters
theta_s = 7.0
theta_b = 2.0
hc = 250
N = 31

print 'Reading ROMS grid'
# Read the fields we need
id = Dataset(roms_grid, 'r')
roms_lon = id.variables['lon_rho'][:,:]
roms_lat = id.variables['lat_rho'][:,:]
roms_h = id.variables['h'][:,:]
roms_mask = id.variables['mask_rho'][:,:]
roms_zice = id.variables['zice'][:,:]
roms_angle = id.variables['angle'][:,:]
id.close()
# Get land/zice mask
open_ocn = copy(roms_mask)
open_ocn[roms_zice!=0] = 0
land_zice = ma.masked_where(open_ocn==1, open_ocn)
# Convert grid to spherical coordinates
roms_x = -(roms_lat+90)*cos(roms_lon*deg2rad+pi/2)
roms_y = (roms_lat+90)*sin(roms_lon*deg2rad+pi/2)
# Find centre in spherical coordinates
x_c = -(lat_c+90)*cos(lon_c*deg2rad+pi/2)
y_c = (lat_c+90)*sin(lon_c*deg2rad+pi/2)
# Build a regular x-y grid and select the missing circle
x_reg_roms, y_reg_roms = meshgrid(linspace(-nbdry, nbdry, num=1000), linspace(-nbdry, nbdry, num=1000))
land_circle = zeros(shape(x_reg_roms))
land_circle = ma.masked_where(sqrt((x_reg_roms-x_c)**2 + (y_reg_roms-y_c)**2) > radius, land_circle)

print 'Building FESOM low-res mesh'
# Mask open ocean
elements_lr, mask_patches_lr = make_patches(fesom_mesh_path_lr, circumpolar=True, mask_cavities=True)
# Unmask ice shelves
patches_lr = iceshelf_mask(elements_lr)
print 'Building FESOM high-res mesh'
elements_hr, mask_patches_hr = make_patches(fesom_mesh_path_hr, circumpolar=True, mask_cavities=True)
patches_hr = iceshelf_mask(elements_hr)

print 'Calculating ice shelf draft'

# ROMS
# Swap sign on existing zice field
roms_draft = -1*roms_zice
# Mask the open ocean and land
roms_draft = ma.masked_where(roms_zice==0, roms_draft)

# FESOM low-res
# Calculate draft at each element, averaged over 3 corners
# Equivalent to depth of surfce layer
fesom_draft_lr = []
for elm in elements_lr:
    if elm.cavity:
        fesom_draft_lr.append(mean([elm.nodes[0].depth, elm.nodes[1].depth, elm.nodes[2].depth]))

# FESOM high-res
fesom_draft_hr = []
for elm in elements_hr:
    if elm.cavity:
        fesom_draft_hr.append(mean([elm.nodes[0].depth, elm.nodes[1].depth, elm.nodes[2].depth]))

print 'Calculating ice shelf melt rate'

# ROMS
id = Dataset(roms_file, 'r')
# Convert from m/s to m/y
roms_melt = id.variables['m'][0,:,:]*sec_per_year
id.close()
# Mask the open ocean and land
roms_melt = ma.masked_where(roms_zice==0, roms_melt)

# FESOM low-res
# Read melt rate at 2D nodes
id = Dataset(fesom_file_lr_i, 'r')
node_melt_lr = id.variables['wnet'][0,:]*sec_per_year
id.close()
# For each element, calculate average over 3 corners
fesom_melt_lr = []
for elm in elements_lr:
    if elm.cavity:
        fesom_melt_lr.append(mean([node_melt_lr[elm.nodes[0].id], node_melt_lr[elm.nodes[1].id], node_melt_lr[elm.nodes[2].id]]))

# FESOM high-res
id = Dataset(fesom_file_hr_i, 'r')
node_melt_hr = id.variables['wnet'][0,:]*sec_per_year
id.close()
fesom_melt_hr = []
for elm in elements_hr:
    if elm.cavity:
        fesom_melt_hr.append(mean([node_melt_hr[elm.nodes[0].id], node_melt_hr[elm.nodes[1].id], node_melt_hr[elm.nodes[2].id]]))

print 'Calculating bottom water temperature'

# ROMS
id = Dataset(roms_file, 'r')
# Read bottom layer
roms_bwtemp = id.variables['temp'][0,0,:,:]
id.close()
# Mask open ocean and land
roms_bwtemp = ma.masked_where(roms_zice==0, roms_bwtemp)

# FESOM low-res
# Read full 3D field to start
id = Dataset(fesom_file_lr_o, 'r')
node_bwtemp_lr = id.variables['temp'][0,:]
id.close()
# Calculate average over 3 corners of each bottom element
fesom_bwtemp_lr = []
for elm in elements_lr:
    if elm.cavity:
        fesom_bwtemp_lr.append(mean([node_bwtemp_lr[elm.nodes[0].find_bottom().id], node_bwtemp_lr[elm.nodes[1].find_bottom().id], node_bwtemp_lr[elm.nodes[2].find_bottom().id]]))

# FESOM high-res
id = Dataset(fesom_file_hr_o, 'r')
node_bwtemp_hr = id.variables['temp'][0,:]
id.close()
fesom_bwtemp_hr = []
for elm in elements_hr:
    if elm.cavity:
        fesom_bwtemp_hr.append(mean([node_bwtemp_hr[elm.nodes[0].find_bottom().id], node_bwtemp_hr[elm.nodes[1].find_bottom().id], node_bwtemp_hr[elm.nodes[2].find_bottom().id]]))    

print 'Calculating bottom water salinity'

# ROMS
id = Dataset(roms_file, 'r')
# Read bottom layer
roms_bwsalt = id.variables['salt'][0,0,:,:]
id.close()
# Mask open ocean and land
roms_bwsalt = ma.masked_where(roms_zice==0, roms_bwsalt)

# FESOM low-res
# Read full 3D field to start
id = Dataset(fesom_file_lr_o, 'r')
node_bwsalt_lr = id.variables['salt'][0,:]
id.close()
# Calculate average over 3 corners of each bottom element
fesom_bwsalt_lr = []
for elm in elements_lr:
    if elm.cavity:
        fesom_bwsalt_lr.append(mean([node_bwsalt_lr[elm.nodes[0].find_bottom().id], node_bwsalt_lr[elm.nodes[1].find_bottom().id], node_bwsalt_lr[elm.nodes[2].find_bottom().id]]))

# FESOM high-res
id = Dataset(fesom_file_hr_o, 'r')
node_bwsalt_hr = id.variables['salt'][0,:]
fesom_bwsalt_hr = []
id.close()
for elm in elements_hr:
    if elm.cavity:
        fesom_bwsalt_hr.append(mean([node_bwsalt_hr[elm.nodes[0].find_bottom().id], node_bwsalt_hr[elm.nodes[1].find_bottom().id], node_bwsalt_hr[elm.nodes[2].find_bottom().id]]))    

print 'Calculating vertically averaged velocity'

# ROMS
# Read full 3D u and v
id = Dataset(roms_file, 'r')
u_3d_tmp = id.variables['u'][0,:,:,:]
v_3d_tmp = id.variables['v'][0,:,:,:]
id.close()
# Get integrands on 3D grid; we only care about dz
dx, dy, dz, z = cartesian_grid_3d(roms_lon, roms_lat, roms_h, roms_zice, theta_s, theta_b, hc, N)
# Unrotate each vertical level
u_3d = ma.empty(shape(dz))
v_3d = ma.empty(shape(dz))
num_lat_u = size(u_3d_tmp,1)
num_lon_u = size(u_3d_tmp,2)
num_lat_v = size(v_3d_tmp,1)
num_lon_v = size(v_3d_tmp,2)
for k in range(N):
    # Extend into land mask before interpolation to rho-grid so
    # the land mask doesn't change in the final plot
    for j in range(1,num_lat_u-1):
        for i in range(1,num_lon_u-1):
            # Check for masked points
            if u_3d_tmp[k,j,i] is ma.masked:
                # Look at 4 neighbours
                neighbours = ma.array([u_3d_tmp[k,j-1,i], u_3d_tmp[k,j,i-1], u_3d_tmp[k,j+1,i], u_3d_tmp[k,j,i+1]])
                # Find how many of them are unmasked
                num_unmasked = MaskedArray.count(neighbours)
                if num_unmasked > 0:
                    # There is at least one unmasked neighbour;
                    # set u_3d_tmp to their average
                    u_3d_tmp[k,j,i] = sum(neighbours)/num_unmasked
    # Repeat for v
    for j in range(1,num_lat_v-1):
        for i in range(1,num_lon_v-1):
            if v_3d_tmp[k,j,i] is ma.masked:
                neighbours = ma.array([v_3d_tmp[k,j-1,i], v_3d_tmp[k,j,i-1], v_3d_tmp[k,j+1,i], v_3d_tmp[k,j,i+1]])
                num_unmasked = MaskedArray.count(neighbours)
                if num_unmasked > 0:
                    v_3d_tmp[k,j,i] = sum(neighbours)/num_unmasked
    # Interpolate to rho grid and rotate
    u_k, v_k = rotate_vector_roms(u_3d_tmp[k,:,:], v_3d_tmp[k,:,:], roms_angle)
    u_3d[k,:,:] = u_k
    v_3d[k,:,:] = v_k
# Vertically average u and v
roms_u = sum(u_3d*dz, axis=0)/sum(dz, axis=0)
roms_v = sum(v_3d*dz, axis=0)/sum(dz, axis=0)
# Mask the open ocean and land
roms_u = ma.masked_where(roms_zice==0, roms_u)
roms_v = ma.masked_where(roms_zice==0, roms_v)
# Calculate speed
roms_speed = sqrt(roms_u**2 + roms_v**2)

# FESOM low-res
# The overlaid vectors are based on nodes not elements, so many
# of the fesom_grid data structures fail to apply and we need to
# read some of the FESOM grid files again.
# Read the cavity flag for each 2D surface node
fesom_cavity_lr = []
f = open(fesom_mesh_path_lr + 'cavity_flag_nod2d.out', 'r')
for line in f:
    tmp = int(line)
    if tmp == 1:
        fesom_cavity_lr.append(True)
    elif tmp == 0:
        fesom_cavity_lr.append(False)
    else:
        print 'Problem'
f.close()
# Save the number of 2D nodes
fesom_n2d_lr = len(fesom_cavity_lr)
# Read rotated lat and lon for each node, also depth
f = open(fesom_mesh_path_lr + 'nod3d.out', 'r')
f.readline()
rlon_lr = []
rlat_lr = []
node_depth_lr = []
for line in f:
    tmp = line.split()
    lon_tmp = float(tmp[1])
    lat_tmp = float(tmp[2])
    node_depth_tmp = -1*float(tmp[3])
    if lon_tmp < -180:
        lon_tmp += 360
    elif lon_tmp > 180:
        lon_tmp -= 360
    rlon_lr.append(lon_tmp)
    rlat_lr.append(lat_tmp)
    node_depth_lr.append(node_depth_tmp)
f.close()
# For lat and lon, only care about the 2D nodes (the first
# fesom_n2d indices)
rlon_lr = array(rlon_lr[0:fesom_n2d_lr])
rlat_lr = array(rlat_lr[0:fesom_n2d_lr])
node_depth_lr = array(node_depth_lr)
# Unrotate longitude
fesom_lon_lr, fesom_lat_lr = unrotate_grid(rlon_lr, rlat_lr)
# Calculate polar coordinates of each node
fesom_x_lr = -(fesom_lat_lr+90)*cos(fesom_lon_lr*deg2rad+pi/2)
fesom_y_lr = (fesom_lat_lr+90)*sin(fesom_lon_lr*deg2rad+pi/2)
# Read lists of which nodes are directly below which
f = open(fesom_mesh_path_lr + 'aux3d.out', 'r')
max_num_layers_lr = int(f.readline())
node_columns_lr = zeros([fesom_n2d_lr, max_num_layers_lr])
for n in range(fesom_n2d_lr):
    for k in range(max_num_layers_lr):
        node_columns_lr[n,k] = int(f.readline())
node_columns_lr = node_columns_lr.astype(int)
f.close()
# Now we can read the data
# Read full 3D field for both u and v
id = Dataset(fesom_file_lr_o, 'r')
node_ur_3d_lr = id.variables['u'][0,:]
node_vr_3d_lr = id.variables['v'][0,:]
id.close()
# Vertically average
node_ur_lr = zeros(fesom_n2d_lr)
node_vr_lr = zeros(fesom_n2d_lr)
for n in range(fesom_n2d_lr):
    # Integrate udz, vdz, and dz over this water column
    udz_col = 0
    vdz_col = 0
    dz_col = 0
    for k in range(max_num_layers_lr-1):
        if node_columns_lr[n,k+1] == -999:
            # Reached the bottom
            break
        # Trapezoidal rule
        top_id = node_columns_lr[n,k]
        bot_id = node_columns_lr[n,k+1]
        dz_tmp = node_depth_lr[bot_id-1] - node_depth_lr[top_id-1]
        udz_col += 0.5*(node_ur_3d_lr[top_id-1]+node_ur_3d_lr[bot_id-1])*dz_tmp
        vdz_col += 0.5*(node_vr_3d_lr[top_id-1]+node_vr_3d_lr[bot_id-1])*dz_tmp
        dz_col += dz_tmp
    # Convert from integrals to averages
    node_ur_lr[n] = udz_col/dz_col
    node_vr_lr[n] = vdz_col/dz_col
# Unrotate
node_u_lr, node_v_lr = unrotate_vector(rlon_lr, rlat_lr, node_ur_lr, node_vr_lr)
# Calculate speed
node_speed_lr = sqrt(node_u_lr**2 + node_v_lr**2)
# Calculate speed at each element, averaged over 3 corners
fesom_speed_lr = []
for elm in elements_lr:
    if elm.cavity:
        fesom_speed_lr.append(mean([node_speed_lr[elm.nodes[0].id], node_speed_lr[elm.nodes[1].id], node_speed_lr[elm.nodes[2].id]]))

# FESOM high-res
fesom_cavity_hr = []
f = open(fesom_mesh_path_hr + 'cavity_flag_nod2d.out', 'r')
for line in f:
    tmp = int(line)
    if tmp == 1:
        fesom_cavity_hr.append(True)
    elif tmp == 0:
        fesom_cavity_hr.append(False)
    else:
        print 'Problem'
f.close()    
fesom_n2d_hr = len(fesom_cavity_hr)
f = open(fesom_mesh_path_hr + 'nod3d.out', 'r')
f.readline()
rlon_hr = []
rlat_hr = []
node_depth_hr = []
for line in f:
    tmp = line.split()
    lon_tmp = float(tmp[1])
    lat_tmp = float(tmp[2])
    node_depth_tmp = -1*float(tmp[3])
    if lon_tmp < -180:
        lon_tmp += 360
    elif lon_tmp > 180:
        lon_tmp -= 360
    rlon_hr.append(lon_tmp)
    rlat_hr.append(lat_tmp)
    node_depth_hr.append(node_depth_tmp)
f.close()
rlon_hr = array(rlon_hr[0:fesom_n2d_hr])
rlat_hr = array(rlat_hr[0:fesom_n2d_hr])
node_depth_hr = array(node_depth_hr)
fesom_lon_hr, fesom_lat_hr = unrotate_grid(rlon_hr, rlat_hr)
fesom_x_hr = -(fesom_lat_hr+90)*cos(fesom_lon_hr*deg2rad+pi/2)
fesom_y_hr = (fesom_lat_hr+90)*sin(fesom_lon_hr*deg2rad+pi/2)
f = open(fesom_mesh_path_hr + 'aux3d.out', 'r')
max_num_layers_hr = int(f.readline())
node_columns_hr = zeros([fesom_n2d_hr, max_num_layers_hr])
for n in range(fesom_n2d_hr):
    for k in range(max_num_layers_hr):
        node_columns_hr[n,k] = int(f.readline())
node_columns_hr = node_columns_hr.astype(int)
f.close()
id = Dataset(fesom_file_hr_o, 'r')
node_ur_3d_hr = id.variables['u'][0,:]
node_vr_3d_hr = id.variables['v'][0,:]
id.close()
node_ur_hr = zeros(fesom_n2d_hr)
node_vr_hr = zeros(fesom_n2d_hr)
for n in range(fesom_n2d_hr):
    udz_col = 0
    vdz_col = 0
    dz_col = 0
    for k in range(max_num_layers_hr-1):
        if node_columns_hr[n,k+1] == -999:
            break
        top_id = node_columns_hr[n,k]
        bot_id = node_columns_hr[n,k+1]
        dz_tmp = node_depth_hr[bot_id-1] - node_depth_hr[top_id-1]
        udz_col += 0.5*(node_ur_3d_hr[top_id-1]+node_ur_3d_hr[bot_id-1])*dz_tmp
        vdz_col += 0.5*(node_vr_3d_hr[top_id-1]+node_vr_3d_hr[bot_id-1])*dz_tmp
        dz_col += dz_tmp
    node_ur_hr[n] = udz_col/dz_col
    node_vr_hr[n] = vdz_col/dz_col
node_u_hr, node_v_hr = unrotate_vector(rlon_hr, rlat_hr, node_ur_hr, node_vr_hr)
node_speed_hr = sqrt(node_u_hr**2 + node_v_hr**2)
fesom_speed_hr = []
for elm in elements_hr:
    if elm.cavity:
        fesom_speed_hr.append(mean([node_speed_hr[elm.nodes[0].id], node_speed_hr[elm.nodes[1].id], node_speed_hr[elm.nodes[2].id]])) 

# **************** USER MODIFIED SECTION ****************
# Filchner-Ronne
x_min_tmp = -14
x_max_tmp = -4.5
y_min_tmp = 1
y_max_tmp = 10
fig = figure(figsize=(8,14))
fig.patch.set_facecolor('white')
# Melt rate
gs_a = GridSpec(1,3)
gs_a.update(left=0.05, right=0.9, bottom=0.735, top=0.89, wspace=0.05)
cbaxes_tmp = fig.add_axes([0.91, 0.755, 0.025, 0.12])
cbar_ticks = arange(0, 6+3, 3)
plot_melt(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, gs_a, cbaxes_tmp, cbar_ticks, [1.5, 4.5, 6], 'a')
# Velocity
x_centres, y_centres, roms_ubin, roms_vbin, fesom_ubin_lr, fesom_vbin_lr, fesom_ubin_hr, fesom_vbin_hr = make_vectors(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, 30)
gs_b = GridSpec(1,3)
gs_b.update(left=0.05, right=0.9, bottom=0.555, top=0.71, wspace=0.05)
cbaxes_tmp = fig.add_axes([0.91, 0.575, 0.025, 0.12])
cbar_ticks = arange(0, 0.2+0.1, 0.1)
plot_velavg(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, gs_b, cbaxes_tmp, cbar_ticks, x_centres, y_centres, roms_ubin, roms_vbin, fesom_ubin_lr, fesom_vbin_lr, fesom_ubin_hr, fesom_vbin_hr, 'b')
# Bottom water temperature
gs_c = GridSpec(1,3)
gs_c.update(left=0.05, right=0.9, bottom=0.375, top=0.53, wspace=0.05)
cbaxes_tmp = fig.add_axes([0.91, 0.395, 0.025, 0.12])
cbar_ticks = arange(-2.6, -1.8+0.4, 0.4)
plot_bwtemp(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, gs_c, cbaxes_tmp, cbar_ticks, 'c')
# Bottom water salinity
gs_d = GridSpec(1,3)
gs_d.update(left=0.05, right=0.9, bottom=0.195, top=0.35, wspace=0.05)
cbaxes_tmp = fig.add_axes([0.91, 0.215, 0.025, 0.12])
cbar_ticks = arange(34.3, 34.7+0.2, 0.2)
plot_bwsalt(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, gs_d, cbaxes_tmp, cbar_ticks, 'd')
# Ice shelf draft
gs_e = GridSpec(1,3)
gs_e.update(left=0.05, right=0.9, bottom=0.015, top=0.17, wspace=0.05)
cbaxes_tmp = fig.add_axes([0.91, 0.035, 0.025, 0.12])
cbar_ticks = arange(500, 1500+500, 500)
plot_draft(x_min_tmp, x_max_tmp, y_min_tmp, y_max_tmp, gs_e, cbaxes_tmp, cbar_ticks, 'e')
suptitle('Filchner-Ronne Ice Shelf', fontsize=30)
fig.show()


def get_min_max (roms_data, fesom_data_lr, fesom_data_hr, x_min, x_max, y_min, y_max):

    # Start with ROMS
    loc = (roms_x >= x_min)*(roms_x <= x_max)*(roms_y >= y_min)*(roms_y <= y_max)
    var_min = amin(roms_data[loc])
    var_max = amax(roms_data[loc])
    # Modify with FESOM
    # Low-res
    i = 0
    for elm in elements_lr:
        if elm.cavity:
            if any(elm.x >= x_min) and any(elm.x <= x_max) and any(elm.y >= y_min) and any(elm.y <= y_max):
                if fesom_data_lr[i] < var_min:
                    var_min = fesom_data_lr[i]
                if fesom_data_lr[i] > var_max:
                    var_max = fesom_data_lr[i]
            i += 1
    # High-res
    i = 0
    for elm in elements_hr:
        if elm.cavity:
            if any(elm.x >= x_min) and any(elm.x <= x_max) and any(elm.y >= y_min) and any(elm.y <= y_max):
                if fesom_data_hr[i] < var_min:
                    var_min = fesom_data_hr[i]
                if fesom_data_hr[i] > var_max:
                    var_max = fesom_data_hr[i]
            i += 1
    return var_min, var_max


def make_vectors (x_min, x_max, y_min, y_max, num_bins):

    # Set up bins (edges)
    x_bins = linspace(x_min, x_max, num=num_bins+1)
    y_bins = linspace(y_min, y_max, num=num_bins+1)
    # Calculate centres of bins (for plotting)
    x_centres = 0.5*(x_bins[:-1] + x_bins[1:])
    y_centres = 0.5*(y_bins[:-1] + y_bins[1:])
    # ROMS
    # First set up arrays to integrate velocity in each bin
    # Simple averaging of all the points inside each bin
    roms_ubin = zeros([size(y_centres), size(x_centres)])
    roms_vbin = zeros([size(y_centres), size(x_centres)])
    roms_num_pts = zeros([size(y_centres), size(x_centres)])
    # First convert to polar coordinates, rotate to account for
    # longitude in circumpolar projection, and convert back to vector
    # components
    theta_roms = arctan2(roms_v, roms_u)
    theta_circ_roms = theta_roms - roms_lon*deg2rad
    u_circ_roms = roms_speed*cos(theta_circ_roms)
    v_circ_roms = roms_speed*sin(theta_circ_roms)
    # Loop over all points (can't find a better way to do this)
    for j in range(size(roms_speed,0)):
        for i in range(size(roms_speed,1)):
            # Make sure data isn't masked (i.e. land or open ocean)
            if u_circ_roms[j,i] is not ma.masked:
                # Check if we're in the region of interest
                if roms_x[j,i] > x_min and roms_x[j,i] < x_max and roms_y[j,i] > y_min and roms_y[j,i] < y_max:
                    # Figure out which bins this falls into
                    x_index = nonzero(x_bins > roms_x[j,i])[0][0]-1
                    y_index = nonzero(y_bins > roms_y[j,i])[0][0]-1
                    # Integrate
                    roms_ubin[y_index, x_index] += u_circ_roms[j,i]
                    roms_vbin[y_index, x_index] += v_circ_roms[j,i]
                    roms_num_pts[y_index, x_index] += 1
    # Convert from sums to averages
    # First mask out points with no data
    roms_ubin = ma.masked_where(roms_num_pts==0, roms_ubin)
    roms_vbin = ma.masked_where(roms_num_pts==0, roms_vbin)
    # Divide everything else by the number of points
    flag = roms_num_pts > 0
    roms_ubin[flag] = roms_ubin[flag]/roms_num_pts[flag]
    roms_vbin[flag] = roms_vbin[flag]/roms_num_pts[flag]
    # FESOM low-res
    fesom_ubin_lr = zeros([size(y_centres), size(x_centres)])
    fesom_vbin_lr = zeros([size(y_centres), size(x_centres)])
    fesom_num_pts_lr = zeros([size(y_centres), size(x_centres)])
    theta_fesom_lr = arctan2(node_v_lr, node_u_lr)
    theta_circ_fesom_lr = theta_fesom_lr - fesom_lon_lr*deg2rad
    u_circ_fesom_lr = node_speed_lr*cos(theta_circ_fesom_lr)
    v_circ_fesom_lr = node_speed_lr*sin(theta_circ_fesom_lr)
    # Loop over 2D nodes to fill in the velocity bins as before
    for n in range(fesom_n2d_lr):
        if fesom_cavity_lr[n]:
            if fesom_x_lr[n] > x_min and fesom_x_lr[n] < x_max and fesom_y_lr[n] > y_min and fesom_y_lr[n] < y_max:
                x_index = nonzero(x_bins > fesom_x_lr[n])[0][0]-1
                y_index = nonzero(y_bins > fesom_y_lr[n])[0][0]-1
                fesom_ubin_lr[y_index, x_index] += u_circ_fesom_lr[n]
                fesom_vbin_lr[y_index, x_index] += v_circ_fesom_lr[n]
                fesom_num_pts_lr[y_index, x_index] += 1
    fesom_ubin_lr = ma.masked_where(fesom_num_pts_lr==0, fesom_ubin_lr)
    fesom_vbin_lr = ma.masked_where(fesom_num_pts_lr==0, fesom_vbin_lr)
    flag = fesom_num_pts_lr > 0
    fesom_ubin_lr[flag] = fesom_ubin_lr[flag]/fesom_num_pts_lr[flag]
    fesom_vbin_lr[flag] = fesom_vbin_lr[flag]/fesom_num_pts_lr[flag]
    # FESOM high-res
    fesom_ubin_hr = zeros([size(y_centres), size(x_centres)])
    fesom_vbin_hr = zeros([size(y_centres), size(x_centres)])
    fesom_num_pts_hr = zeros([size(y_centres), size(x_centres)])
    theta_fesom_hr = arctan2(node_v_hr, node_u_hr)
    theta_circ_fesom_hr = theta_fesom_hr - fesom_lon_hr*deg2rad
    u_circ_fesom_hr = node_speed_hr*cos(theta_circ_fesom_hr)
    v_circ_fesom_hr = node_speed_hr*sin(theta_circ_fesom_hr)
    for n in range(fesom_n2d_hr):
        if fesom_cavity_hr[n]:
            if fesom_x_hr[n] > x_min and fesom_x_hr[n] < x_max and fesom_y_hr[n] > y_min and fesom_y_hr[n] < y_max:
                x_index = nonzero(x_bins > fesom_x_hr[n])[0][0]-1
                y_index = nonzero(y_bins > fesom_y_hr[n])[0][0]-1
                fesom_ubin_hr[y_index, x_index] += u_circ_fesom_hr[n]
                fesom_vbin_hr[y_index, x_index] += v_circ_fesom_hr[n]
                fesom_num_pts_hr[y_index, x_index] += 1
    fesom_ubin_hr = ma.masked_where(fesom_num_pts_hr==0, fesom_ubin_hr)
    fesom_vbin_hr = ma.masked_where(fesom_num_pts_hr==0, fesom_vbin_hr)
    flag = fesom_num_pts_hr > 0
    fesom_ubin_hr[flag] = fesom_ubin_hr[flag]/fesom_num_pts_hr[flag]
    fesom_vbin_hr[flag] = fesom_vbin_hr[flag]/fesom_num_pts_hr[flag]

    return x_centres, y_centres, roms_ubin, roms_vbin, fesom_ubin_lr, fesom_vbin_lr, fesom_ubin_hr, fesom_vbin_hr


def plot_draft (x_min, x_max, y_min, y_max, gs, cbaxes, cbar_ticks, letter):

    # Set up a grey square for FESOM to fill the background with land
    x_reg_fesom, y_reg_fesom = meshgrid(linspace(x_min, x_max, num=100), linspace(y_min, y_max, num=100))
    land_square = zeros(shape(x_reg_fesom))
    # Find bounds on variable in this region
    var_min, var_max = get_min_max(roms_draft, fesom_draft_lr, fesom_draft_hr, x_min, x_max, y_min, y_max)

    # MetROMS
    ax = subplot(gs[0,0], aspect='equal')
    # First shade land and zice in grey
    contourf(roms_x, roms_y, land_zice, 1, colors=(('0.6', '0.6', '0.6')))
    # Fill in the missing circle
    contourf(x_reg_roms, y_reg_roms, land_circle, 1, colors=(('0.6', '0.6', '0.6')))
    # Now shade the data
    pcolor(roms_x, roms_y, roms_draft, vmin=var_min, vmax=var_max, cmap='jet')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')

    # FESOM low-res
    ax = subplot(gs[0,1], aspect='equal')
    # Start with land background
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    # Add ice shelf elements
    img = PatchCollection(patches_lr, cmap='jet')
    img.set_array(array(fesom_draft_lr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    # Mask out the open ocean in white
    overlay = PatchCollection(mask_patches_lr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Main title
    title(letter + ') Ice shelf draft (m)', fontsize=20)

    # FESOM high-res
    ax = subplot(gs[0,2], aspect='equal')
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    img = PatchCollection(patches_hr, cmap='jet')
    img.set_array(array(fesom_draft_hr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    overlay = PatchCollection(mask_patches_hr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Colourbar on the right
    cbar = colorbar(img, cax=cbaxes, ticks=cbar_ticks)


def plot_melt (x_min, x_max, y_min, y_max, gs, cbaxes, cbar_ticks, change_points, letter):

    # Set up a grey square for FESOM to fill the background with land
    x_reg_fesom, y_reg_fesom = meshgrid(linspace(x_min, x_max, num=100), linspace(y_min, y_max, num=100))
    land_square = zeros(shape(x_reg_fesom))
    # Find bounds on variable in this region
    var_min, var_max = get_min_max(roms_melt, fesom_melt_lr, fesom_melt_hr, x_min, x_max, y_min, y_max)
    # Special colour map
    if var_min < 0:
        # There is refreezing here; include blue for elements < 0
        cmap_vals = array([var_min, 0, change_points[0], change_points[1], change_points[2], var_max])
        cmap_colors = [(0.26, 0.45, 0.86), (1, 1, 1), (1, 0.9, 0.4), (0.99, 0.59, 0.18), (0.5, 0.0, 0.08), (0.96, 0.17, 0.89)]
        cmap_vals_norm = (cmap_vals - var_min)/(var_max - var_min)
        cmap_vals_norm[-1] = 1
        cmap_list = []
        for i in range(size(cmap_vals)):
            cmap_list.append((cmap_vals_norm[i], cmap_colors[i]))
        mf_cmap = LinearSegmentedColormap.from_list('melt_freeze', cmap_list)
    else:
        # No refreezing
        cmap_vals = array([0, change_points[0], change_points[1], change_points[2], var_max])
        cmap_colors = [(1, 1, 1), (1, 0.9, 0.4), (0.99, 0.59, 0.18), (0.5, 0.0, 0.08), (0.96, 0.17, 0.89)]
        cmap_vals_norm = cmap_vals/var_max
        cmap_vals_norm[-1] = 1
        cmap_list = []
        for i in range(size(cmap_vals)):
            cmap_list.append((cmap_vals_norm[i], cmap_colors[i]))
        mf_cmap = LinearSegmentedColormap.from_list('melt_freeze', cmap_list)

    # Plot MetROMS
    ax = subplot(gs[0,0], aspect='equal')
    # First shade land and zice in grey
    contourf(roms_x, roms_y, land_zice, 1, colors=(('0.6', '0.6', '0.6')))
    # Fill in the missing circle
    contourf(x_reg_roms, y_reg_roms, land_circle, 1, colors=(('0.6', '0.6', '0.6')))
    # Now shade the data
    pcolor(roms_x, roms_y, roms_melt, vmin=var_min, vmax=var_max, cmap=mf_cmap)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Melt rate is always at the top, so add model labels
    text(0.5, 1.25, 'MetROMS', fontsize=18, horizontalalignment='center', transform=ax.transAxes) 

    # FESOM low-res
    ax = subplot(gs[0,1], aspect='equal')
    # Start with land background
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    # Add ice shelf elements
    img = PatchCollection(patches_lr, cmap=mf_cmap)
    img.set_array(array(fesom_melt_lr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    # Mask out the open ocean in white
    overlay = PatchCollection(mask_patches_lr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    title(letter + ') Ice shelf melt rate (m/y)', fontsize=20)
    text(0.5, 1.25, 'FESOM (low-res)', fontsize=18, horizontalalignment='center', transform=ax.transAxes) 

    # FESOM high-res
    ax = subplot(gs[0,2], aspect='equal')
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    img = PatchCollection(patches_hr, cmap=mf_cmap)
    img.set_array(array(fesom_melt_hr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    overlay = PatchCollection(mask_patches_hr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Colourbar on the right
    cbar = colorbar(img, cax=cbaxes, ticks=cbar_ticks)
    text(0.5, 1.25, 'FESOM (high-res)', fontsize=18, horizontalalignment='center', transform=ax.transAxes) 


def plot_bwtemp (x_min, x_max, y_min, y_max, gs, cbaxes, cbar_ticks, letter):

    # Set up a grey square for FESOM to fill the background with land
    x_reg_fesom, y_reg_fesom = meshgrid(linspace(x_min, x_max, num=100), linspace(y_min, y_max, num=100))
    land_square = zeros(shape(x_reg_fesom))
    # Find bounds on variable in this region
    var_min, var_max = get_min_max(roms_bwtemp, fesom_bwtemp_lr, fesom_bwtemp_hr, x_min, x_max, y_min, y_max)

    # Plot MetROMS
    ax = subplot(gs[0,0], aspect='equal')
    # First shade land and zice in grey
    contourf(roms_x, roms_y, land_zice, 1, colors=(('0.6', '0.6', '0.6')))
    # Fill in the missing circle
    contourf(x_reg_roms, y_reg_roms, land_circle, 1, colors=(('0.6', '0.6', '0.6')))
    # Now shade the data
    pcolor(roms_x, roms_y, roms_bwtemp, vmin=var_min, vmax=var_max, cmap='jet')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')

    # FESOM low-res
    ax = subplot(gs[0,1], aspect='equal')
    # Start with land background
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    # Add ice shelf elements
    img = PatchCollection(patches_lr, cmap='jet')
    img.set_array(array(fesom_bwtemp_lr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    # Mask out the open ocean in white
    overlay = PatchCollection(mask_patches_lr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Main title
    title(letter + r') Bottom water temperature ($^{\circ}$C)', fontsize=20)

    # FESOM high-res
    ax = subplot(gs[0,2], aspect='equal')
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    img = PatchCollection(patches_hr, cmap='jet')
    img.set_array(array(fesom_bwtemp_hr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    overlay = PatchCollection(mask_patches_hr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Colourbar on the right
    cbar = colorbar(img, cax=cbaxes, ticks=cbar_ticks)
    

def plot_bwsalt (x_min, x_max, y_min, y_max, gs, cbaxes, cbar_ticks, letter):

    # Set up a grey square for FESOM to fill the background with land
    x_reg_fesom, y_reg_fesom = meshgrid(linspace(x_min, x_max, num=100), linspace(y_min, y_max, num=100))
    land_square = zeros(shape(x_reg_fesom))
    # Find bounds on variable in this region
    var_min, var_max = get_min_max(roms_bwsalt, fesom_bwsalt_lr, fesom_bwsalt_hr, x_min, x_max, y_min, y_max)

    # Plot MetROMS
    ax = subplot(gs[0,0], aspect='equal')
    # First shade land and zice in grey
    contourf(roms_x, roms_y, land_zice, 1, colors=(('0.6', '0.6', '0.6')))
    # Fill in the missing circle
    contourf(x_reg_roms, y_reg_roms, land_circle, 1, colors=(('0.6', '0.6', '0.6')))
    # Now shade the data
    pcolor(roms_x, roms_y, roms_bwsalt, vmin=var_min, vmax=var_max, cmap='jet')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')

    # FESOM low-res
    ax = subplot(gs[0,1], aspect='equal')
    # Start with land background
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    # Add ice shelf elements
    img = PatchCollection(patches_lr, cmap='jet')
    img.set_array(array(fesom_bwsalt_lr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    # Mask out the open ocean in white
    overlay = PatchCollection(mask_patches_lr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Main title
    title(letter + ') Bottom water salinity (psu)', fontsize=20)

    # FESOM high-res
    ax = subplot(gs[0,2], aspect='equal')
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    img = PatchCollection(patches_hr, cmap='jet')
    img.set_array(array(fesom_bwsalt_hr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    overlay = PatchCollection(mask_patches_hr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Colourbar on the right
    cbar = colorbar(img, cax=cbaxes, ticks=cbar_ticks)


def plot_velavg (x_min, x_max, y_min, y_max, gs, cbaxes, cbar_ticks, x_centres, y_centres, roms_ubin, roms_vbin, fesom_ubin_lr, fesom_vbin_lr, fesom_ubin_hr, fesom_vbin_hr, letter, loc_string=None):

    # Set up a grey square for FESOM to fill the background with land
    x_reg_fesom, y_reg_fesom = meshgrid(linspace(x_min, x_max, num=100), linspace(y_min, y_max, num=100))
    land_square = zeros(shape(x_reg_fesom))
    # Find bounds on variable in this region
    var_min, var_max = get_min_max(roms_speed, fesom_speed_lr, fesom_speed_hr, x_min, x_max, y_min, y_max)

    # Plot MetROMS
    ax = subplot(gs[0,0], aspect='equal')
    # First shade land and zice in grey
    contourf(roms_x, roms_y, land_zice, 1, colors=(('0.6', '0.6', '0.6')))
    # Fill in the missing circle
    contourf(x_reg_roms, y_reg_roms, land_circle, 1, colors=(('0.6', '0.6', '0.6')))
    # Now shade the data
    pcolor(roms_x, roms_y, roms_speed, vmin=var_min, vmax=var_max, cmap='cool')
    # Overlay vectors
    quiver(x_centres, y_centres, roms_ubin, roms_vbin, scale=1.5, headwidth=6, headlength=7, color='black')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')

    # FESOM low-res
    ax = subplot(gs[0,1], aspect='equal')
    # Start with land background
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    # Add ice shelf elements
    img = PatchCollection(patches_lr, cmap='cool')
    img.set_array(array(fesom_speed_lr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    # Mask out the open ocean in white
    overlay = PatchCollection(mask_patches_lr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    # Overlay vectors
    quiver(x_centres, y_centres, fesom_ubin_lr, fesom_vbin_lr, scale=1.5, headwidth=6, headlength=7, color='black')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Main title
    if loc_string is None:
        title(letter + ') Vertically averaged ocean velocity (m/s)', fontsize=20)
    else:
        title(letter + ') Vertically averaged ocean velocity (m/s): '+loc_string, fontsize=20)

    # FESOM high-res
    ax = subplot(gs[0,2], aspect='equal')
    contourf(x_reg_fesom, y_reg_fesom, land_square, 1, colors=(('0.6', '0.6', '0.6')))
    img = PatchCollection(patches_hr, cmap='cool')
    img.set_array(array(fesom_speed_hr))
    img.set_edgecolor('face')
    img.set_clim(vmin=var_min, vmax=var_max)
    ax.add_collection(img)
    overlay = PatchCollection(mask_patches_hr, facecolor=(1,1,1))
    overlay.set_edgecolor('face')
    ax.add_collection(overlay)
    quiver(x_centres, y_centres, fesom_ubin_hr, fesom_vbin_hr, scale=1.5, headwidth=6, headlength=7, color='black')
    xlim([x_min, x_max])
    ylim([y_min, y_max])
    axis('off')
    # Colourbar on the right
    cbar = colorbar(img, cax=cbaxes, ticks=cbar_ticks)


def plot_zonal_ts (lon0, lat_min, lat_max, depth_min, depth_max, gs1, gs2, cbaxes1, cbaxes2, cbar_ticks1, cbar_ticks2, letter1, letter2, loc_string=None):

    # Figure out what to write on the title about longitude
    if lon0 < 0:
        lon_string = str(-lon0)+r'$^{\circ}$W'
    else:
        lon_string = str(lon0)+r'$^{\circ}$E'

    # ROMS
    # Read temperature and salinity
    id = Dataset(roms_file, 'r')
    roms_temp_3d = id.variables['temp'][-1,:,:,:]
    roms_salt_3d = id.variables['salt'][-1,:,:,:]
    id.close()
    # Get a 3D array of z-coordinates; sc_r and Cs_r are unused in this script
    roms_z_3d, sc_r, Cs_r = calc_z(roms_h, roms_zice, theta_s, theta_b, hc, N)
    # Make sure we are in the range 0-360
    if lon0 < 0:
        lon0 += 360
    # Interpolate to lon0
    roms_temp, roms_z_1d, roms_lat_1d = interp_lon_roms(roms_temp_3d, roms_z_3d, roms_lat, roms_lon, lon0)
    roms_salt, roms_z_1d, roms_lat_1d = interp_lon_roms(roms_salt_3d, roms_z_3d, roms_lat, roms_lon, lon0)
    # Switch back to range -180-180
    if lon0 > 180:
        lon0 -= 360

    # FESOM low-res
    # Read temperature and salinity
    id = Dataset(fesom_file_lr_o, 'r')
    fesom_temp_nodes_lr = id.variables['temp'][-1,:]
    fesom_salt_nodes_lr = id.variables['salt'][-1,:]
    id.close()
    # Build arrays of SideElements making up zonal slices
    selements_temp_lr = fesom_sidegrid(elements_lr, fesom_temp_nodes_lr, lon0, lat_max)
    selements_salt_lr = fesom_sidegrid(elements_lr, fesom_salt_nodes_lr, lon0, lat_max)
    # Build array of quadrilateral patches for the plots, and data values
    # corresponding to each SideElement
    patches_lr = []
    fesom_temp_lr = []
    for selm in selements_temp_lr:
        # Make patch
        coord = transpose(vstack((selm.y, selm.z)))
        patches_lr.append(Polygon(coord, True, linewidth=0.))
        # Save data value
        fesom_temp_lr.append(selm.var)
    fesom_temp_lr = array(fesom_temp_lr)
    # Salinity has same patches but different values
    fesom_salt_lr = []
    for selm in selements_salt_lr:
        fesom_salt_lr.append(selm.var)
    fesom_salt_lr = array(fesom_salt_lr)

    # FESOM high-res
    id = Dataset(fesom_file_hr_o, 'r')
    fesom_temp_nodes_hr = id.variables['temp'][-1,:]
    fesom_salt_nodes_hr = id.variables['salt'][-1,:]
    id.close()
    selements_temp_hr = fesom_sidegrid(elements_hr, fesom_temp_nodes_hr, lon0, lat_max)
    selements_salt_hr = fesom_sidegrid(elements_hr, fesom_salt_nodes_hr, lon0, lat_max)
    patches_hr = []
    fesom_temp_hr = []
    for selm in selements_temp_hr:
        coord = transpose(vstack((selm.y, selm.z)))
        patches_hr.append(Polygon(coord, True, linewidth=0.))
        fesom_temp_hr.append(selm.var)
    fesom_temp_hr = array(fesom_temp_hr)
    fesom_salt_hr = []
    for selm in selements_salt_hr:
        fesom_salt_hr.append(selm.var)
    fesom_salt_hr = array(fesom_salt_hr)

    # Find bounds on each variable
    temp_min = amin(array([amin(roms_temp[flag]), amin(fesom_temp_lr), amin(fesom_temp_hr)]))
    temp_max = amax(array([amax(roms_temp[flag]), amax(fesom_temp_lr), amax(fesom_temp_hr)]))
    salt_min = amin(array([amin(roms_salt[flag]), amin(fesom_salt_lr), amin(fesom_salt_hr)]))
    salt_max = amax(array([amax(roms_salt[flag]), amax(fesom_salt_lr), amax(fesom_salt_hr)]))

    # Plot temperature
    # MetROMS
    ax = subplot(gs1[0,0])
    pcolor(roms_lat_1d, roms_z_1d, roms_temp, vmin=temp_min, vmax=temp_max, cmap='jet')
    ylabel('Depth (m)', fontsize=16)
    xlabel('Latitude', fontsize=16)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])

    # FESOM low-res
    ax = subplot(gs1[0,1])
    img = PatchCollection(patches_lr, cmap='jet')
    img.set_array(fesom_temp_lr)
    img.set_edgecolor('face')
    img.set_clim(vmin=temp_min, vmax=temp_max)
    ax.add_collection(img)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    if loc_string is None:
        title(letter1 + r') Temperature ($^{\circ}$C) through ' + lon_string, fontsize=20)
    else:
        title(letter1 + r') Temperature ($^{\circ}$C) through ' + lon_string + ': ' + loc_string, fontsize=20)

    # FESOM high-res
    ax = subplot(gs1[0,2])
    img = PatchCollection(patches_hr, cmap='jet')
    img.set_array(fesom_temp_hr)
    img.set_edgecolor('face')
    img.set_clim(vmin=temp_min, vmax=temp_max)
    ax.add_collection(img)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    # Add a colorbar
    cbar = colorbar(img, cax=cbaxes1, ticks=cbar_ticks1)

    # Plot salinity
    # MetROMS
    ax = subplot(gs2[0,0])
    pcolor(roms_lat_1d, roms_z_1d, roms_salt, vmin=salt_min, vmax=salt_max, cmap='jet')
    ylabel('Depth (m)', fontsize=16)
    xlabel('Latitude', fontsize=16)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])
    # FESOM low-res
    ax = subplot(gs2[0,1])
    img = PatchCollection(patches_lr, cmap='jet')
    img.set_array(fesom_salt_lr)
    img.set_edgecolor('face')
    img.set_clim(vmin=salt_min, vmax=salt_max)
    ax.add_collection(img)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    if loc_string is None:
        title(letter2 + ') Salinity (psu) through ' + lon_string, fontsize=20)
    else:
        title(letter2 + ') Salnity (psu) through ' + lon_string + ': ' + loc_string, fontsize=20)
    # FESOM high-res
    ax = subplot(gs2[0,2])
    img = PatchCollection(patches_hr, cmap='jet')
    img.set_array(fesom_salt_hr)
    img.set_edgecolor('face')
    img.set_clim(vmin=salt_min, vmax=salt_max)
    ax.add_collection(img)
    xlim([lat_min, lat_max])
    ylim([depth_min, depth_max])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    # Add a colorbar
    cbar = colorbar(img, cax=cbaxes2, ticks=cbar_ticks2)
    
    
    
    

    
