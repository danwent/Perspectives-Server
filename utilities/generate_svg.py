import time
from xml.dom.minidom import parseString

colors = [ "blue","purple","yellow","orange","cyan", "red", "brown" ]


def setup_color_info(server_result_list,cutoff,color_info): 
	key_to_ts_list = {} 
	for s in server_result_list:
		if s["results"] is None: 
			continue
		notary_reply = parseString(s["results"]).documentElement
		for k in notary_reply.getElementsByTagName("key"): 
        		fingerprint = k.getAttribute("fp")
			if not fingerprint in key_to_ts_list:  
				key_to_ts_list[fingerprint] = []
        		timespans = k.getElementsByTagName("timestamp")
			for ts in timespans: 
				key_to_ts_list[fingerprint].append(int(ts.getAttribute("end")))
			
		most_recent_list = []
		for key in key_to_ts_list: 
			key_to_ts_list[key].sort(reverse=True)
			most_recent_ts = key_to_ts_list[key][0]; 
			if most_recent_ts >= cutoff:  
				most_recent_list.append({ "key" : key, "ts" : most_recent_ts })
		
		def most_recent_ts_cmp(a, b): 
			return b["ts"] - a["ts"]
 
		most_recent_list.sort(cmp=most_recent_ts_cmp)
		color_count = 0
		while color_count < len(most_recent_list) and color_count < len(colors):
			fp = most_recent_list[color_count]["key"]  
			color_info[fp] = colors[color_count] 
			color_count += 1
	return color_count
	
 

def get_svg_graph(service_id, server_result_list, len_days,cur_secs): 
	x_offset = 200
	y_offset = 40 
	width = 700
	y_cord = y_offset
	pixels_per_day = (width - x_offset - 20) / len_days 
	rec_height = 10 
	grey_used = False
	cutoff = cur_secs - (len_days * 24 * 60 * 60)
	color_info = {}
	color_count = setup_color_info(server_result_list, cutoff,color_info)
	height = (color_count * 30) + (len(server_result_list) * 20) + y_offset + 60

	tmp_x = x_offset + 70 
	res =  """<?xml version="1.0"?>
		<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" 
			"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
		<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="%s" height="%s">
		<rect x="0" y="0" width="%s" height="%s" fill="white" />
			<text x="%s" y="%s" font-size="15" > Key History (Days) </text>   
			<text x="4" y="%s" font-size="15">Notary and Current Key</text>""" % \
			(width, height, width, height, (x_offset + 70), y_cord, y_cord) 

	y_cord += 20
	for s in server_result_list:
		most_recent_color = "white" # none
		most_recent_end = 0
		y_cord += 20
		res += '<text x="4" y="' + str(y_cord + 8) + '" font-size="10">' + \
				s["host"] + '</text>\n'
		
		if s["results"] is None: 
			# print "current key" circle as empty white   
			res += """<rect x="%s" y="%s" width="10" height="10" 
				fill="%s" rx="5" stroke="black" stroke-width="1px" />\n""" % \
  				((x_offset - 30), y_cord, "white")
			continue
		notary_reply = parseString(s["results"]).documentElement
		for obs in notary_reply.getElementsByTagName("key"): 
        		fingerprint = obs.getAttribute("fp")
			color = color_info.get(fingerprint,"grey")

			for ts in obs.getElementsByTagName("timestamp"):  
				t_start = int(ts.getAttribute("start"))
				t_end = int(ts.getAttribute("end"))
				if t_end < cutoff:
					continue
				if t_start < cutoff: 
					t_start = cutoff # draw partial 
				if t_end > most_recent_end: 
					most_recent_end = t_end
					most_recent_color = color
				if color == "grey": 
					grey_used = True 
				time_since = cur_secs - t_end 
				duration = t_end - t_start 
				x_cord = x_offset + int(pixels_per_day * (time_since / (24 * 3600)))
				span_width = pixels_per_day * (float(duration) / (24 * 3600)) 
				# a timespan with no width is not shown        
				if span_width > 0:          
					res += """<rect 	x="%s" y="%s" width="%s" height="%s" fill="%s" rx="1" 
							stroke="black" stroke-width="1px" />\n""" %  \
						(x_cord,y_cord,span_width,rec_height, color)	
    
		# print "current key" circle      
		res += """<rect x="%s" y="%s" width="10" height="10" 
				fill="%s" rx="5" stroke="black" stroke-width="1px" />\n""" % \
  				((x_offset - 30), y_cord, most_recent_color)
	# draw Days axis  
	for i in xrange(10):  
		days = int(i * (len_days / 10.0))
		x = x_offset + (pixels_per_day * days)
		y = y_offset + 30    
		res += '<text x="%s" y="%s" font-size="15">%s</text>\n' % (x,y,days)
		res += '<path d = "M %s %s L %s %s" stroke = "grey" stroke-width = "1"/>\n' % (x,y,x,(y_cord + 20))

	# draw legend mapping colors to keys
	y_cord += 30
	if grey_used: 
		color_info["all other keys"] = "grey" 
	for key in color_info: 
		res += """<rect x="%s" y="%s" width="10" height="10" fill="%s"
				rx="0" stroke="black" stroke-width="1px" />
			  	<text x="%s" y="%s" font-size="13"> %s </text>
		 	""" % (x_offset, y_cord, color_info[key],(x_offset + 15),(y_cord + 9), key)
		y_cord += 20
 
	res += '</svg>' 
	return res


