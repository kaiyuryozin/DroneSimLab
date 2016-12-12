# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
import zmq,pickle,time
import config

if __name__!="__main__":
    from Wrappers import phandlers as ph
    import numpy as np
    import cv2

context = zmq.Context()

show_cv=False
pub_cv=True

drone_subs=[]
for ind in range(config.n_drones):
    socket_sub = context.socket(zmq.SUB)
    _,port=config.zmq_pub_drone_fdm
    drone_ip='172.17.0.%d'%(ind+2) #172.17.0.1 for the docker host and 172.17.0.2 for first drone etc...
    #drone_ip='127.0.0.%d'%(ind+1) #172.17.0.1 for the docker host and 172.17.0.2 for first drone etc...
    addr='tcp://%s:%d'%(drone_ip,port)
    print("connecting to",addr)
    socket_sub.connect(addr)
    socket_sub.setsockopt(zmq.SUBSCRIBE,config.topic_sitl_position_report)
    drone_subs.append(socket_sub)

socket_pub = context.socket(zmq.PUB)
socket_pub.bind("tcp://*:%d" % config.zmq_pub_unreal_proxy[1] )


start=time.time()

def main_loop(gworld):
    print('-- actors --')
    for p in ph.GetActorsNames(gworld):
        print(p)
    print('-- textures --')
    drone_textures=[]
    drone_textures.append(ph.GetTextureByName('/Game/TextureRenderTarget2D'))
    drone_textures.append(ph.GetTextureByName('/Game/TextureRenderTarget2D_2'))
    if not all(drone_textures):
        print("Error, Could not find all textures")
        while 1:
            yield
    drone_actors=[]
    drone_actors.append(ph.FindActorByName(gworld,'Parrot_Drone_6'))
    drone_actors.append(ph.FindActorByName(gworld,'Parrot_Drone2'))
    if not all(drone_actors):
        print("Error, Could not find all drone actors")
        while 1:
            yield
    
    for _ in range(10): #need to send it a few time don't know why.
        socket_pub.send_multipart([config.topic_unreal_state,b'main_loop'])
        yield
    drone_start_positions=[np.array(ph.GetActorLocation(drone_actor)) for drone_actor in drone_actors]
    positions=[None for _ in range(config.n_drones)]
    while 1:
        for drone_index in range(config.n_drones):
            socket_sub=drone_subs[drone_index]
            drone_actor=drone_actors[drone_index]
            while len(zmq.select([socket_sub],[],[],0)[0])>0:
                topic, msg = socket_sub.recv_multipart()
                positions[drone_index]=pickle.loads(msg)
            position=positions[drone_index] 
            if position is not None:
                new_pos=drone_start_positions[drone_index]+np.array([position['posx'],position['posy'],position['posz']])*100 #turn to cm
                ph.SetActorLocation(drone_actor,new_pos)
                ph.SetActorRotation(drone_actor,(position['roll'],position['pitch'],position['yaw']))
                positions[drone_index]=None
        yield
        for drone_index in range(config.n_drones):
            img=cv2.resize(ph.GetTextureData(drone_textures[drone_index]),(256,256),cv2.INTER_LINEAR)
            if pub_cv:
                socket_pub.send_multipart([config.topic_unreal_drone_rgb_camera%drone_index,pickle.dumps(img,-1)])
            if show_cv:
                cv2.imshow('drone camera %d'%drone_index,img)
                cv2.waitKey(1)

def kill():
    print('done!')
    socket_pub.send_multipart([config.topic_unreal_state,b'kill'])
    if show_cv:
        cv2.destroyAllWindows()
        for _ in range(10):
            cv2.waitKey(10)



if __name__=="__main__":
    while 1:
        for drone_index in range(config.n_drones):
            socket_sub=drone_subs[drone_index]
            while len(zmq.select([socket_sub],[],[],0)[0])>0:
                topic, msg = socket_sub.recv_multipart()
                print("got ",topic)

