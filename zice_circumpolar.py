from netCDF4 import Dataset
from numpy import *
from matplotlib.pyplot import *
from matplotlib.colors import ListedColormap

# Creates a circumpolar Antarctic plot of ice shelf draft.
# Input:
# grid_path = path to ROMS grid file
# fig_name = filename for figure
def zice_circumpolar (grid_path, fig_name):

    deg2rad = pi/180
    # Northern boundary 63S for plot
    nbdry = -60+90
    # Centre of missing circle in grid
    lon_c = 50
    lat_c = -83
    # Radius of missing circle (play around with this until it works)
    radius = 10.1

    # Read data
    id = Dataset(grid_path, 'r')
    zice = -1*id.variables['zice'][:-15,:-1]
    lon = id.variables['lon_rho'][:-15,:-1]
    lat = id.variables['lat_rho'][:-15,:-1]
    mask_rho = id.variables['mask_rho'][:-15,:-1]
    id.close()

    # Mask the open ocean and land
    zice = ma.masked_where(zice==0, zice)
    # Get land/zice mask
    open_ocn = copy(mask_rho)
    open_ocn[zice!=0] = 0
    land_zice = ma.masked_where(open_ocn==1, open_ocn)

    # Convert to spherical coordinates
    x = -(lat+90)*cos(lon*deg2rad+pi/2)
    y = (lat+90)*sin(lon*deg2rad+pi/2)
    # Find centre in spherical coordinates
    x_c = -(lat_c+90)*cos(lon_c*deg2rad+pi/2)
    y_c = (lat_c+90)*sin(lon_c*deg2rad+pi/2)
    # Build a regular x-y grid and select the missing circle
    x_reg, y_reg = meshgrid(linspace(-nbdry, nbdry, num=1000), linspace(-nbdry, nbdry, num=1000))
    land_circle = zeros(shape(x_reg))
    land_circle = ma.masked_where(sqrt((x_reg-x_c)**2 + (y_reg-y_c)**2) > radius, land_circle)

    # Plot
    fig = figure(figsize=(128,96))
    ax = fig.add_subplot(1,1,1, aspect='equal')
    fig.patch.set_facecolor('white')
    # First shade land and zice in grey (include zice so there are no white
    # patches near the grounding line where contours meet)
    grey_cmap = ListedColormap([(0.6, 0.6, 0.6)])
    pcolor(x, y, land_zice, cmap=grey_cmap)
    pcolor(x_reg, y_reg, land_circle, cmap=grey_cmap)
    # Now shade zice
    img = pcolor(x, y, zice, vmin=0, vmax=2300, cmap='jet')
    cbar = colorbar(img, extend='max')
    cbar.ax.tick_params(labelsize=160)
    xlim([-nbdry, nbdry])
    ylim([-nbdry, nbdry])
    title('Ice shelf draft (m)', fontsize=240)
    axis('off')

    #show()
    fig.savefig(fig_name)


# Command-line interface
if __name__ == "__main__":

    grid_path = raw_input("Path to ROMS grid file: ")
    fig_name = raw_input("Filename for figure: ")
    zice_circumpolar(grid_path, fig_name)    
