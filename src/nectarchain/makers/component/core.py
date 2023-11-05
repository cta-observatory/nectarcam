import logging

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
log.handlers = logging.getLogger("__main__").handlers

import numpy as np
from abc import ABC, abstractmethod
import copy
from tables.exceptions import NoSuchNodeError
from pathlib import Path

from ctapipe.core import Component,TelescopeComponent
from ctapipe.instrument import CameraGeometry
from ctapipe.containers import EventType
from ctapipe.core.traits import Unicode,Integer,ComponentNameList


from ctapipe_io_nectarcam.containers import NectarCAMDataContainer
from ctapipe_io_nectarcam import NectarCAMEventSource, constants
from ctapipe.containers import EventType,Container
from ctapipe.io import HDF5TableReader


from ...data.container.core import ArrayDataContainer
from ...data.container import (ChargesContainer,
                               ChargesContainers,
                               TriggerMapContainer,
                               ArrayDataContainer,
                               WaveformsContainer,
                               WaveformsContainers
                               )

__all__ = ["ArrayDataComponent",
           "NectarCAMComponent",
           "get_valid_component",
           ]

def get_valid_component() : 
    return NectarCAMComponent.non_abstract_subclasses()


            
class NectarCAMComponent(TelescopeComponent) : 
    """The base class for NectarCAM components"""
    SubComponents = ComponentNameList(
        Component,
        default_value = None,
        allow_none = True,
        read_only = True,                           
        help="List of Component names that are used insite current component, this is used to resolve recusively the configurable traits defined in sub-components"
    ).tag(config=True)

    def __init__(self, subarray, config=None, parent=None,*args, **kwargs):
        super().__init__(subarray = subarray, config = config, parent = parent, *args,**kwargs)
        self.__pixels_id = parent._event_source.camera_config.expected_pixels_id
        self.__run_number = parent.run_number
        self.__npixels=parent.npixels
    
    @abstractmethod
    def __call__(
            self, event: NectarCAMDataContainer, *args, **kwargs
        ):
        pass

    @property
    def _pixels_id(self) : return self.__pixels_id
    @property
    def pixels_id(self) : return copy.deepcopy(self.__pixels_id)
    @property
    def _run_number(self) :
        return self.__run_number
    @property
    def run_number(self) :
        return copy.deepcopy(self.__run_number)
    @property
    def _npixels(self) :
        return self.__npixels
    @property
    def npixels(self) :
        return copy.deepcopy(self.__npixels)

class ArrayDataComponent(NectarCAMComponent) :
    TEL_ID = Integer(default_value = 0,
                     help = "The telescope ID",
                     read_only = True,
                     ).tag(config = True)

    CAMERA_NAME = Unicode(default_value = "NectarCam-003",
                     help = "The camera name",
                     read_only = True,
                     ).tag(config = True)

    CAMERA = CameraGeometry.from_name(CAMERA_NAME.default_value)

    #trigger_list = List(
    #    help="List of trigger(EventType) inside the instance",
    #    default_value=[],
    #).tag(config=True)



    def __init__(self, subarray, config=None, parent=None,*args, **kwargs):
        super().__init__(subarray = subarray,config = config, parent = parent,*args, **kwargs)
        self.__nsamples = parent._event_source.camera_config.num_samples


        self.trigger_list = []

        # data we want to compute
        self.__ucts_timestamp = {}
        self.__ucts_busy_counter = {}
        self.__ucts_event_counter = {}
        self.__event_type = {}
        self.__event_id = {}
        self.__trig_patter_all = {}
        self.__broken_pixels_hg = {}
        self.__broken_pixels_lg = {}

    def _init_trigger_type(self, trigger: EventType, **kwargs):
        """
        Initializes empty lists for different trigger types in the ArrayDataMaker class.

        Args:
            trigger (EventType): The trigger type for which the lists are being initialized.

        Returns:
            None. The method only initializes the empty lists for the trigger type.
        """
        name = __class__._get_name_trigger(trigger)
        self.__ucts_timestamp[f"{name}"] = []
        self.__ucts_busy_counter[f"{name}"] = []
        self.__ucts_event_counter[f"{name}"] = []
        self.__event_type[f"{name}"] = []
        self.__event_id[f"{name}"] = []
        self.__trig_patter_all[f"{name}"] = []
        self.__broken_pixels_hg[f"{name}"] = []
        self.__broken_pixels_lg[f"{name}"] = []
        self.trigger_list.append(trigger)

    @staticmethod
    def _compute_broken_pixels(wfs_hg, wfs_lg, **kwargs):
        """
        Computes broken pixels for high and low gain waveforms.
        Args:
            wfs_hg (ndarray): High gain waveforms.
            wfs_lg (ndarray): Low gain waveforms.
            **kwargs: Additional keyword arguments.
        Returns:
            tuple: Two arrays of zeros with the same shape as `wfs_hg` (or `wfs_lg`) but without the last dimension.
        """
        log.warning("computation of broken pixels is not yet implemented")
        return np.zeros((wfs_hg.shape[:-1]), dtype=bool), np.zeros(
            (wfs_hg.shape[:-1]), dtype=bool
        )

    @staticmethod
    def _compute_broken_pixels_event(
        event: NectarCAMDataContainer, pixels_id: np.ndarray, **kwargs
    ):
        """
        Computes broken pixels for a specific event and pixel IDs.
        Args:
            event (NectarCAMDataContainer): An event.
            pixels_id (list or np.ndarray): IDs of pixels.
            **kwargs: Additional keyword arguments.
        Returns:
            tuple: Two arrays of zeros with the length of `pixels_id`.
        """
        log.warning("computation of broken pixels is not yet implemented")
        return np.zeros((len(pixels_id)), dtype=bool), np.zeros(
            (len(pixels_id)), dtype=bool
        )

    @staticmethod
    def _get_name_trigger(trigger: EventType):
        """
        Gets the name of a trigger event.
        Args:
            trigger (EventType): A trigger event.
        Returns:
            str: The name of the trigger event.
        """
        if trigger is None:
            name = "None"
        else:
            name = trigger.name
        return name

    def __call__(
        self, event: NectarCAMDataContainer, *args, **kwargs
    ):
        """
        Method to extract data from the event.

        Args:
            event (NectarCAMDataContainer): The event object.
            trigger (EventType): The trigger type.
            *args: Additional arguments that can be passed to the method.
            **kwargs: Additional keyword arguments that can be passed to the method.

        Returns:
            If the return_wfs keyword argument is True, the method returns the high and low gain waveforms from the event.
        """
        name = __class__._get_name_trigger(event.trigger.event_type)

        if not(name in self.__event_id.keys()) : 
            self._init_trigger_type(event.trigger.event_type)

        self.__event_id[f"{name}"].append(np.uint32(event.index.event_id))
        self.__ucts_timestamp[f"{name}"].append(
            event.nectarcam.tel[__class__.TEL_ID.default_value].evt.ucts_timestamp
        )
        self.__event_type[f"{name}"].append(event.trigger.event_type.value)
        self.__ucts_busy_counter[f"{name}"].append(
            event.nectarcam.tel[__class__.TEL_ID.default_value].evt.ucts_busy_counter
        )
        self.__ucts_event_counter[f"{name}"].append(
            event.nectarcam.tel[__class__.TEL_ID.default_value].evt.ucts_event_counter
        )
        self.__trig_patter_all[f"{name}"].append(
            event.nectarcam.tel[__class__.TEL_ID.default_value].evt.trigger_pattern.T
        )

        if kwargs.get("return_wfs", False):
            get_wfs_hg = event.r0.tel[0].waveform[constants.HIGH_GAIN][self.pixels_id]
            get_wfs_lg = event.r0.tel[0].waveform[constants.LOW_GAIN][self.pixels_id]
            return get_wfs_hg, get_wfs_lg

    

    @abstractmethod
    def finish(self):
        pass

    @staticmethod
    def select_container_array_field(
        container: ArrayDataContainer, pixel_id: np.ndarray, field: str
    ) -> np.ndarray:
        """
        Selects specific fields from an ArrayDataContainer object based on a given list of pixel IDs.

        Args:
            container (ArrayDataContainer): An object of type ArrayDataContainer that contains the data.
            pixel_id (ndarray): An array of pixel IDs for which the data needs to be selected.
            field (str): The name of the field to be selected from the container.

        Returns:
            ndarray: An array containing the selected data for the given pixel IDs.
        """
        mask_contain_pixels_id = np.array(
            [pixel in container.pixels_id for pixel in pixel_id], dtype=bool
        )
        for pixel in pixel_id[~mask_contain_pixels_id]:
            log.warning(
                f"You asked for pixel_id {pixel} but it is not present in this container, skip this one"
            )
        res = np.array(
            [
                np.take(
                    container[field],
                    np.where(container.pixels_id == pixel)[0][0],
                    axis=1,
                )
                for pixel in pixel_id[mask_contain_pixels_id]
            ]
        )
        ####could be nice to return np.ma.masked_array(data = res, mask = container.broken_pixels_hg.transpose(res.shape[1],res.shape[0],res.shape[2]))
        return res

    @staticmethod
    def merge_along_slices(
        containers: TriggerMapContainer
        ) -> ArrayDataContainer:
        keys_list = list(containers.containers.keys())
        merged_containers = containers.containers[keys_list[0]]
        for trigger in merged_containers.containers.keys() : 
            for key in keys_list[1:] : 
                if trigger in containers.containers[key].containers.keys() :
                    merged_containers.containers[trigger] =  __class__.merge(merged_containers.containers[trigger],containers.containers[key].containers[trigger])
                for new_trigger in containers.containers[key].containers.keys() : 
                    if not(new_trigger in merged_containers.containers.keys()) : 
                        merged_containers.containers[new_trigger] = containers.containers[key].containers[new_trigger]
        return merged_containers

    @staticmethod
    def merge(
        container_a: ArrayDataContainer, container_b: ArrayDataContainer
    ) -> ArrayDataContainer:
        """method to merge 2 ArrayDataContainer into one single ArrayDataContainer

        Returns:
            ArrayDataContainer: the merged object
        """
        if type(container_a) != type(container_b):
            raise Exception("The containers have to be instnace of the same class")

        if not(np.array_equal(container_a.pixels_id, container_b.pixels_id)):
            raise Exception("The containers have not the same pixels ids")

        merged_container = container_a.__class__()

        for field in container_a.keys():
            if not(isinstance(container_a[field], np.ndarray)):
                if field!="nevents" and (container_a[field] != container_b[field]):
                    raise Exception(
                        f"merge impossible because of {field} filed (values are {container_a[field]} and {container_b[field]}"
                    )

        for field in container_a.keys():
            if isinstance(container_a[field], np.ndarray):
                if field!="pixels_id" : 
                    merged_container[field] = np.concatenate(
                        (container_a[field], container_b[field]), axis=0
                    )
                else : 
                    merged_container[field] = container_a[field]
            else:
                if field=="nevents" : 
                    merged_container[field] = container_a[field] + container_b[field]
                else : 
                    merged_container[field] = container_a[field]

        return merged_container
    


    @staticmethod
    def _container_from_hdf5(path,slice_index = None,container_class = ArrayDataContainer) : 
        if isinstance(path,str) : 
            path = Path(path)
        
        container = eval(f"{container_class.__name__}s")()
        

        with HDF5TableReader(path) as reader : 
            if slice_index is None or len(reader._h5file.root.__members__) > 1 : 
                for data in reader._h5file.root.__members__ : 
                    container.containers[data] = eval(f"{container_class.__name__}s")()
                    for key,trigger in EventType.__members__.items() : 
                        try : 
                            waveforms_data = eval(f"reader._h5file.root.{data}.__members__") 
                            _mask = [container_class.__name__ in _word for _word in waveforms_data] 
                            _waveforms_data = np.array(waveforms_data)[_mask]
                            if len(_waveforms_data) == 1 : 
                                tableReader = reader.read(table_name = f"/{data}/{_waveforms_data[0]}/{trigger.name}", containers = container_class)
                                container.containers[data].containers[trigger] = next(tableReader)
                            else : 
                                log.info(f"there is {len(_waveforms_data)} entry corresponding to a {container_class} table save, unable to load")
                        except NoSuchNodeError as err:
                            log.warning(err)
                        except Exception as err:
                            log.error(err,exc_info = True)
                            raise err
            else : 
                data = "data" if slice_index is None else f"data_{slice_index}"
                for key,trigger in EventType.__members__.items() : 
                    try : 
                        container_data = eval(f"reader._h5file.root.{data}.__members__") 
                        _mask = [container_class.__name__ in _word for _word in container_data] 
                        _container_data = container_data[_mask]
                        if len(_container_data) == 1 : 
                            tableReader = reader.read(table_name = f"/{data}/{_container_data[0]}/{trigger.name}", containers = container_class)
                            container.containers[trigger] = next(tableReader)
                        else : 
                            log.info(f"there is {len(_container_data)} entry corresponding to a {container_class} table save, unable to load")
                    except NoSuchNodeError as err:
                        log.warning(err)
                    except Exception as err:
                        log.error(err,exc_info = True)
                        raise err
        return container


    @property
    def nsamples(self):
        """
        Returns a deep copy of the nsamples attribute.

        Returns:
            np.ndarray: A deep copy of the nsamples attribute.
        """
        return copy.deepcopy(self.__nsamples)

    @property
    def _nsamples(self):
        """
        Returns the nsamples attribute.

        Returns:
            np.ndarray: The nsamples attribute.
        """
        return self.__nsamples
    

    def nevents(self, trigger: EventType):
        """
        Returns the number of events for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the number of events is requested.

        Returns:
            int: The number of events for the specified trigger type.
        """
        return ArrayDataContainer.fields['nevents'].type(len(self.__event_id[__class__._get_name_trigger(trigger)]))

    @property
    def _broken_pixels_hg(self):
        """
        Returns the broken_pixels_hg attribute.

        Returns:
            np.ndarray: The broken_pixels_hg attribute.
        """
        return self.__broken_pixels_hg

    def broken_pixels_hg(self, trigger: EventType):
        """
        Returns an array of broken pixels for high gain for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the broken pixels for high gain are requested.

        Returns:
            np.ndarray: An array of broken pixels for high gain for the specified trigger type.
        """
        return np.array(
            self.__broken_pixels_hg[__class__._get_name_trigger(trigger)], dtype=ArrayDataContainer.fields['broken_pixels_hg'].dtype
        )

    @property
    def _broken_pixels_lg(self):
        """
        Returns the broken_pixels_lg attribute.

        Returns:
            np.ndarray: The broken_pixels_lg attribute.
        """
        return self.__broken_pixels_lg

    def broken_pixels_lg(self, trigger: EventType):
        """
        Returns an array of broken pixels for low gain for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the broken pixels for low gain are requested.

        Returns:
            np.ndarray: An array of broken pixels for low gain for the specified trigger type.
        """
        return np.array(
            self.__broken_pixels_lg[__class__._get_name_trigger(trigger)], dtype=ArrayDataContainer.fields['broken_pixels_lg'].dtype
        )

    def ucts_timestamp(self, trigger: EventType):
        """
        Returns an array of UCTS timestamps for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the UCTS timestamps are requested.

        Returns:
            np.ndarray: An array of UCTS timestamps for the specified trigger type.
        """
        return np.array(
            self.__ucts_timestamp[__class__._get_name_trigger(trigger)], dtype=ArrayDataContainer.fields['ucts_timestamp'].dtype
        )

    def ucts_busy_counter(self, trigger: EventType):
        """
        Returns an array of UCTS busy counters for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the UCTS busy counters are requested.

        Returns:
            np.ndarray: An array of UCTS busy counters for the specified trigger type.
        """
        return np.array(
            self.__ucts_busy_counter[__class__._get_name_trigger(trigger)],
            dtype=ArrayDataContainer.fields['ucts_busy_counter'].dtype,
        )

    def ucts_event_counter(self, trigger: EventType):
        """
        Returns an array of UCTS event counters for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the UCTS event counters are requested.

        Returns:
            np.ndarray: An array of UCTS event counters for the specified trigger type.
        """
        return np.array(
            self.__ucts_event_counter[__class__._get_name_trigger(trigger)],
            dtype=ArrayDataContainer.fields['ucts_event_counter'].dtype,
        )

    def event_type(self, trigger: EventType):
        """
        Returns an array of event types for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the event types are requested.

        Returns:
            np.ndarray: An array of event types for the specified trigger type.
        """
        return np.array(
            self.__event_type[__class__._get_name_trigger(trigger)], dtype=ArrayDataContainer.fields['event_type'].dtype
        )

    def event_id(self, trigger: EventType):
        """
        Returns an array of event IDs for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the event IDs are requested.

        Returns:
            np.ndarray: An array of event IDs for the specified trigger type.
        """
        return np.array(
            self.__event_id[__class__._get_name_trigger(trigger)], dtype=ArrayDataContainer.fields['event_id'].dtype
        )

    def multiplicity(self, trigger: EventType):
        """
        Returns an array of multiplicities for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the multiplicities are requested.

        Returns:
            np.ndarray: An array of multiplicities for the specified trigger type.
        """
        tmp = self.trig_pattern(trigger)
        if len(tmp) == 0:
            return np.array([])
        else:
            return ArrayDataContainer.fields['multiplicity'].dtype.type(np.count_nonzero(tmp, axis=1))

    def trig_pattern(self, trigger: EventType):
        """
        Returns an array of trigger patterns for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the trigger patterns are requested.

        Returns:
            np.ndarray: An array of trigger patterns for the specified trigger type.
        """
        tmp = self.trig_pattern_all(trigger)
        if len(tmp) == 0:
            return np.array([])
        else:
            return tmp.any(axis=2)

    def trig_pattern_all(self, trigger: EventType):
        """
        Returns an array of trigger patterns for all events for the specified trigger type.

        Args:
            trigger (EventType): The trigger type for which the trigger patterns for all events are requested.

        Returns:
            np.ndarray: An array of trigger patterns for all events for the specified trigger type.
        """
        return np.array(
            self.__trig_patter_all[f"{__class__._get_name_trigger(trigger)}"],
            dtype=ArrayDataContainer.fields['trig_pattern_all'].dtype,
        )

    