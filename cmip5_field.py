from numpy import *
from netCDF4 import Dataset, num2date, date2num
from os import listdir
from scipy.interpolate import interp1d

# Read CMIP5 output for the given model, experiment, and variable name.
# Input:
# model = Model object (class definition in cmip5_paths.py)
# expt = string containing name of experiment, eg 'historical'
# var_name = string containing name of variable, eg 'tas'
# start_year, end_year = integers containing years to average over, from the
#                        beginning of start_year to the end of end_year. 
#                        Therefore, if start_year = end_year, this script will
#                        average over one year of model output.
# Output:
# data_trimmed = array of model output, with dimension time x latitude x
#                longitude (for atmosphere variables, at the surface) or
#                time x depth x latitude x longitude (for ocean variables),
#                possibly with units converted to be more comparable to other 
#                models and/or reanalyses
# lon, lat = longitude and latitude arrays (1D or 2D)
# depth = depth array (1D or 3D) if ocean variable, otherwise None
# month_indices = 1D array containing the month indices (1 to 12) of each time
#                 index in data_trimmed
def cmip5_field (model, expt, var_name, start_year, end_year):

    # Northern boundary of ROMS
    nbdry = -30
    # Conversion from K to C
    degKtoC = -273.15

    # Figure out whether it is an atmosphere or ocean variable
    if var_name in ['ps', 'tas', 'huss', 'clt', 'uas', 'vas', 'pr', 'prsn', 'evspsbl', 'rsds', 'rlds']:
        realm = 'atmos'
    elif var_name in ['thetao', 'so', 'uo', 'vo', 'zos']:
        realm = 'ocean'
    else:
        print 'Unknown variable'
        # Exit early
        return None, None, None, None, None

    # There is something weird going on with evaporation in the Norwegian GCMs;
    # they claim to have units of kg/m^2/s but there's no way that's correct.
    # Exclude them for now, until we figure out what the units actually are.
    if var_name == 'evspsbl' and model.name in ['NorESM1-M', 'NorESM1-ME']:
        print 'Skipping ' + model.name + ' because evaporation units are screwy'
        # Exit early
        return None, None, None, None, None

    # Get the directory where the model output is stored
    path = model.get_directory(expt, var_name)
    # If the string is empty, this output doesn't exist
    if path == '':
        print 'Warning: no data found for model ' + model.name + ', experiment ' + expt + ', variable ' + var_name
        # Exit early
        return None, None, None, None, None

    # 1D array of time values (as datetime objects); initialise as None and
    # then add to it with each file
    time = None
    # Similarly, a 3D array of data values (time x lat x lon for atmosphere
    # variables, time x depth x lat x lon for ocean variables)
    data = None

    # Loop over all files in this directory
    for file in listdir(path):

        # Check every netCDF file
        if file.endswith('.nc'):

            # Read the time values
            id = Dataset(path + file, 'r')
            time_id = id.variables['time']
            if amin(time_id[:]) < 0:
                # Missing values here; this occurs for one 1900-1949 file
                # We can just skip it
                break
            # Convert to datetime objects
            curr_units = time_id.units
            if curr_units == 'days since 0001-01':
                curr_units = 'days since 0001-01-01'
            if curr_units == 'days since 0000-01-01 00:00:00':
                curr_units = 'days since 0001-01-01 00:00:00'
            time_tmp = num2date(time_id[:], units=curr_units, calendar=time_id.calendar)

            # Check if the time values in this file actually contain any
            # dates we're interested in
            if time_tmp[0].year > end_year or time_tmp[-1].year < start_year:
                # No overlap, skip this file and go to the next one
                id.close()
            else:
                # Initialise master time array if it doesn't exist yet,
                # otherwise add the new time values to the end.
                if time is None:
                    time = time_tmp[:]
                else:
                    time = concatenate((time, time_tmp), axis=0)

                # Read the grid
                lat = id.variables['lat'][:]
                lon = id.variables['lon'][:]
                if realm == 'ocean':
                    if model.name == 'inmcm4':
                        # inmcm4 has sigma coordinates; convert to z
                        sigma = id.variables['lev'][:]
                        h = id.variables['depth'][:,:]
                        depth = ma.empty([size(sigma), size(h,0), size(h,1)])
                        for k in range(size(sigma)):
                            depth[k,:,:] = -sigma[k]*h
                    else:
                        depth = id.variables['lev'][:]
                else:
                    depth = None

                # Read model output
                data_tmp = id.variables[var_name][:]
                # Some of the CMIP5 ocean models are not saved as masked
                # arrays, but rather as regular arrays with the value 0
                # at all land points. Catch these with a try-except block
                # and convert to masked arrays.
                try:
                    mask = data_tmp.mask
                except (AttributeError):
                    data_tmp = ma.masked_where(data_tmp==0, data_tmp)
                # Initialise the master data array if it doesn't exist yet,
                # otherwise add the new data values to the end
                if data is None:
                    data = data_tmp
                else:
                    data = ma.concatenate((data, data_tmp), axis=0)

    # Check if we actually read any data
    if time is None or data is None:
        print 'No files found in specified date range'
        # Exit early
        return None, None, None, None, None

    # Figure out how many time indices are between the dates we're interested in
    num_time = 0
    for t in time:
        if t.year >= start_year and t.year <= end_year:
            num_time += 1
    # Set up data array with the correct number of time indices
    if realm == 'atmos':
        data_trimmed = ma.empty([num_time, size(data,1), size(data,2)])
    elif realm == 'ocean':
        data_trimmed = ma.empty([num_time, size(data,1), size(data,2), size(data,3)])
    # Also set up array of corresponding months
    month_indices = []

    # Sort the data chronologically
    # First convert the datetime objects back to floats, just for the purpose
    # of sorting; the calendar doesn't matter as long as it's consistent
    time_floats = date2num(time, units='days since 0001-01-01 00:00:00', calendar='standard')
    # We won't necessarily keep all of the data, so first just find the indices
    # of the sorted time array, eg [1 7 3 6] would have sorted indices [0 2 3 1]
    sort_index = argsort(time_floats)

    # Initialise next available time index in data_trimmed
    posn = 0
    # Loop over each time index
    for index in sort_index:
        # Figure out if it falls between the dates we're interested in
        if time[index].year >= start_year and time[index].year <= end_year:
            # Save model output at this time index to the new array
            if realm == 'atmos':
                data_trimmed[posn,:,:] = data[index,:,:]
            elif realm == 'ocean':
                data_trimmed[posn,:,:,:] = data[index,:,:,:]
            # Save month index
            month_indices.append(time[index].month)
            posn += 1

    # Conversions if necessary
    if var_name in ['pr', 'prsn', 'evspsbl']:
        # Convert precip/snowfall/evap from kg/m^2/s to
        # 1e-6 kg/m^2/s
        data_trimmed = 1e6*data_trimmed
    elif var_name == 'ps':
        # Convert surface pressure from Pa to kPa
        data_trimmed = 1e-3*data_trimmed
    elif var_name == 'tas':
        # Convert temperature from K to C
        data_trimmed = data_trimmed + degKtoC
    elif var_name == 'thetao' and amin(data_trimmed) > 100:
        # Convert ocean temperature from K to C if needed
        data_trimmed = data_trimmed + degKtoC
    elif var_name == 'so' and amax(data_trimmed) < 1:
        # Convert salinity from fraction to psu if needed
        data_trimmed = 1e3*data_trimmed

    return data_trimmed, lon, lat, depth, month_indices
    

    
