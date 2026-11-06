import osmnx as ox, time
ox.settings.use_cache=True; ox.settings.cache_folder='data/raw/osm_cache'; ox.settings.requests_timeout=300
t=time.time()
G=ox.graph_from_bbox((-79.70,43.575,-79.105,43.86),network_type='drive',simplify=True,retain_all=False,truncate_by_edge=True)
print(len(G.nodes),len(G.edges),time.time()-t)
ox.save_graphml(G,'data/interim/toronto_drive.graphml')
