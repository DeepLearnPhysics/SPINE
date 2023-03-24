import numpy as np
import h5py
import yaml

class HDF5Reader:
    '''
    Class which reads back information stored in HDF5 files.

    More documentation to come.
    '''
    
    def __init__(self, file_paths, entry_list=[], skip_entry_list=[], larcv_particles=False):
        '''
        Load up the HDF5 file.

        Parameters
        ----------
        file_paths : list
            List of paths to the HDF5 files to be read
        entry_list: list(int)
            Entry IDs to be accessed
        skip_entry_list: list(int)
            Entry IDs to be skipped
        '''
        # Make sure the file path(s) is(are) provided in the form of a list
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        # Loop over the input files, build a map from index to file ID
        self.file_paths  = file_paths
        self.file_index  = []
        self.num_entries = 0
        for i, path in enumerate(file_paths):
            with h5py.File(path, 'r') as file:
                assert 'events' in file, 'File does not contain an event tree'
                self.num_entries += len(file['events'])
                self.file_index.append(i*np.ones(len(file['events']), dtype=np.int32))
        self.file_index = np.concatenate(self.file_index)

        # Build an entry list to access
        self.entry_list = self.get_entry_list(entry_list, skip_entry_list)
        self.file_index = self.file_index[self.entry_list]

        # Set whether or not to load true particle objects as LArCV particles
        self.larcv_particles = larcv_particles

    def __len__(self):
        '''
        Returns the number of entries in the file

        Returns
        -------
        int
            Number of entries in the file
        '''
        return self.num_entries

    def __getitem__(self, idx):
        '''
        Returns a specific entry in the file

        Parameters
        ----------
        idx : int
            Integer entry ID to access

        Returns
        -------
        data_blob : dict
            Ditionary of input data products corresponding to one event
        result_blob : dict
            Ditionary of result data products corresponding to one event
        '''
        return self.get(idx)

    def get(self, idx, nested=False):
        '''
        Returns a specific entry in the file

        Parameters
        ----------
        idx : int
            Integer entry ID to access
        nested : bool
            If true, nest the output in an array of length 1 (for analysis tools)

        Returns
        -------
        data_blob : dict
            Ditionary of input data products corresponding to one event
        result_blob : dict
            Ditionary of result data products corresponding to one event
        '''
        # Get the appropriate entry index
        assert idx < len(self.entry_list)
        entry_idx = self.entry_list[idx]
        file_idx  = self.file_index[idx]

        # Use the events tree to find out what needs to be loaded
        data_blob, result_blob = {}, {}
        with h5py.File(self.file_paths[file_idx], 'r') as file:
            event = file['events'][entry_idx]
            for key in event.dtype.names:
                self.load_key(file, event, data_blob, result_blob, key, nested)

        return data_blob, result_blob

    def get_entry_list(self, entry_list, skip_entry_list):
        '''
        Create a list of events that can be accessed by `self.get`

        Parameters
        ----------
        entry_list : list
            List of integer entry IDs to add to the index
        skip_entry_list : list
            List of integer entry IDs to skip from the index

        Returns
        -------
        list
            List of integer entry IDs in the index
        '''
        if not entry_list:
            entry_list = np.arange(self.num_entries, dtype=int)
        if skip_entry_list:
            assert np.all(np.asarray(entry_list) < self.num_entries)
            entry_list = set(entry_list)
            for s in skip_entry_list:
                if s in entry_list:
                    entry_list.pop(s)
            entry_list = list(entry_list)
        
        assert len(entry_list), 'Must at least have one entry to load'
        return entry_list

    def load_key(self, file, event, data_blob, result_blob, key, nested):
        '''
        Fetch a specific key for a specific event.

        Parameters
        ----------
        file : h5py.File
            HDF5 file instance
        event : dict
            Dictionary of objects that make up one event
        data_blob : dict
            Dictionary used to store the loaded input data
        result_blob : dict
            Dictionary used to store the loaded result data
        key: str
            Name of the dataset in the event
        nested : bool
            If true, nest the output in an array of length 1 (for analysis tools)
        '''
        # The event-level information is a region reference: fetch it
        region_ref = event[key]
        cat = 'data' if key in file['data'] else 'result'
        blob = data_blob if cat == 'data' else result_blob
        group = file[cat]
        if isinstance(group[key], h5py.Dataset):
            if not group[key].dtype.names:
                # If the reference points at a simple dataset, return
                blob[key] = group[key][region_ref]
            else:
                # If the dataset has multiple attributes, it contains particle info
                array = group[key][region_ref]
                names = array.dtype.names
                if self.larcv_particles:
                    blob[key] = self.make_larcv_particles(array, names)
                else:
                    blob[key] = []
                    for i in range(len(array)):
                        blob[key].append(dict(zip(names, array[i])))
        else:
            # If the reference points at a group, unpack
            el_refs = group[key]['index'][region_ref].flatten()
            if len(group[key]['index'].shape) == 1:
                ret = [group[key]['elements'][r] for r in el_refs]
            else:
                ret = [group[key][f'element_{i}'][r] for i, r in enumerate(el_refs)]
            blob[key] = ret

        if nested:
            blob[key] = [blob[key]]

    @staticmethod
    def make_larcv_particles(array, names):
        '''
        Rebuild `larcv.Particle` objects from the stored information

        Parameters
        ----------
        array : list
            List of dictionary of particle information
        names: 
            List of class attribute names

        Returns
        -------
        list
            List of filled larcv.Particle objects
        '''
        from larcv import larcv
        ret = []
        for i in range(len(array)):
            # Initialize new larcv.Particle object
            part_dict = array[i]
            particle = larcv.Particle()

            # Momentum is particular, deal with it first
            particle.momentum(part_dict['px'], part_dict['py'], part_dict['pz'])
            for name in names:
                if name in ['px', 'py', 'pz', 'p']:
                    continue # Addressed by the momentum setter
                if 'position' in name or 'step' in name:
                    getattr(particle, name)(*part_dict[name])
                else:
                    cast = lambda x: x.item() if type(x) != bytes and not isinstance(x, np.ndarray) else x
                    getattr(particle, name)(cast(part_dict[name]))

            ret.append(particle)

        return ret
