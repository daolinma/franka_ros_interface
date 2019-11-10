
import tf
import numpy as np
import quaternion
from franka_control.srv import SetEEFrame
import rospy
import franka_dataflow

from collections import namedtuple
_FRAME_NAMES = namedtuple('Constants', ['EE_FRAME', 'K_FRAME'])
DEFAULT_TRANSFORMATIONS = _FRAME_NAMES( [0.707099974155426, -0.707099974155426, 0.0, 0.0, 0.707099974155426, 0.707099974155426, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.10339999943971634, 1.0], 
                                        None)

# DEFAULT_EE_FRAME = [0.707099974155426, -0.707099974155426, 0.0, 0.0, 0.707099974155426, 0.707099974155426, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.10339999943971634, 1.0] # default when the franka_ros control is launched

class FrankaFramesInterface():
    """
        Helper class to retrieve and set EE frames, [and K frame (not implemented)]

        Has to be updated externally each time franka states is updated. This is done by default within the PandaArm class.

        Note that all controllers have to be unloaded before switching frames. This has to be done externally.

    """

    def __init__(self):
        self._current_EE_frame_transformation = None
        


    def set_EE_frame(self, frame):
        """
        Set new EE frame based on the transformation given by 'frame', which is the 
        transformation matrix defining the new desired EE frame with respect to the flange frame.

        @type frame: [float (16,)] / np.ndarray (4x4) 
        @param frame: transformation matrix of new EE frame wrt flange frame (column major)
        @rtype: bool
        @return: success status of service request
        """
        frame = self._assert_frame_validity(frame)

        return self._request_setEE_service(frame)


    def _update_frame_data(self, EE_frame_transformation, K_frame_transformation = None):

        assert len(EE_frame_transformation) == 16, "FrankaFramesInterface: Current EE frame transformation could not be retrieved!"
        self._current_EE_frame_transformation = EE_frame_transformation

    def _assert_frame_validity(self, frame):

        if isinstance(frame, np.ndarray):
            if frame.shape[0] == frame.shape[1] == 4:
                frame = frame.flatten('F').tolist()
            else:
                raise ValueError("Invalid shape for transformation matrix numpy array")
        else:
            assert len(frame) == 16, "Invalid number of elements in transformation matrix. Should have 16 elements."

        return frame

    def set_EE_frame_to_link(self, frame_name, timeout = 5.0):
        """
        Set new EE frame to the same frame as the link frame given by 'frame_name'
        Motion controllers are stopped for switching

        @type frame_name: str 
        @param frame_name: desired tf frame name in the tf tree
        @rtype: [bool, str]
        @return: [success status of service request, error msg if any]
        """

        trans = False
        listener = tf.TransformListener()
        err = "FrankaFramesInterface: Error while looking up transform from Flange frame to link frame %s"%frame_name
        def body():
            try:
                listener.lookupTransform('/panda_link8', frame_name, rospy.Time(0))
            except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException) as e:
                err = e
                return False
            return True

        franka_dataflow.wait_for(lambda: body(), timeout = timeout, raise_on_error = True, timeout_msg = err)

        t,rot = listener.lookupTransform('/panda_link8', frame_name, rospy.Time(0))

        rot = np.quaternion(rot[3],rot[0],rot[1],rot[2])

        rot = quaternion.as_rotation_matrix(rot)

        trans_mat = np.eye(4)

        trans_mat[:3,:3] = rot
        trans_mat[:3,3] = np.array(t)

        return self.set_EE_frame(trans_mat)



    def get_EE_frame(self, as_mat = False):
        """
        Get current EE frame transformation matrix in flange frame
        
        @type as_mat: bool
        @param as_mat: if True, return np array, else as list
        @rtype: [float (16,)] / np.ndarray (4x4) 
        @return: transformation matrix of EE frame wrt flange frame (column major)
        """
        return self._current_EE_frame_transformation if not as_mat else np.asarray(self._current_EE_frame_transformation).reshape(4,4,order='F')

    def reset_EE_frame(self):
        """
        Reset EE frame to default. (defined by DEFAULT_TRANSFORMATIONS.EE_FRAME global variable defined above) 

        @rtype: bool
        @return: success status of service request
        """
        return self.set_EE_frame(frame = DEFAULT_TRANSFORMATIONS.EE_FRAME)

    def EE_frame_is_reset(self):
        assert self._current_EE_frame_transformation is not None, "FrankaFramesInterface: Current EE Frame is not known."
        return list(self._current_EE_frame_transformation) == list(DEFAULT_TRANSFORMATIONS.EE_FRAME)
        

    def _request_setEE_service(self, trans_mat):

        rospy.wait_for_service('/franka_ros_interface/franka_control/set_EE_frame')
        try:
            service_handle = rospy.ServiceProxy('/franka_ros_interface/franka_control/set_EE_frame', SetEEFrame)
            response = service_handle(F_T_EE = trans_mat)
            rospy.loginfo("Set EE Frame Request Status: %s. \n\tDetails: %s"%("Success" if response.success else "Failed!", response.error))
            return response.success
        except rospy.ServiceException, e:
            rospy.logwarn("Set EE Frame Request: Service call failed: %s"%e)
            return False


    def set_K_frame(self, frame):
        """
        Set new K frame based on the transformation given by 'frame', which is the 
        transformation matrix defining the new desired K frame with respect to the EE frame.

        @type frame: [float (16,)] / np.ndarray (4x4) 
        @param frame: transformation matrix of new K frame wrt EE frame
        @rtype: bool
        @return: success status of service request
        """
        raise NotImplementedError("Not defined yet")
        

    def get_K_frame(self, as_mat = False):
        """
        Get current K frame transformation matrix in EE frame
        
        @type as_mat: bool
        @param as_mat: if True, return np array, else as list
        @rtype: [float (16,)] / np.ndarray (4x4) 
        @return: transformation matrix of K frame wrt EE frame
        """
        raise NotImplementedError("Not defined yet")

    def reset_K_frame(self):
        """
        Reset K frame to default. (defined by DEFAULT_K_ FRAME global variable defined above) 

        @rtype: bool
        @return: success status of service request
        """

        raise NotImplementedError("Not defined yet")


if __name__ == '__main__':
    # main()
    from franka_interface import ArmInterface

    rospy.init_node("test")

    ee_setter = FrankaFramesInterface(ArmInterface())

    # ee_setter.set_EE_frame([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])

    