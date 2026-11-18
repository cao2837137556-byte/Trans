"""Regression cases for joint component selection, strict admission, and g4 placement."""
import numpy as np


def run():
    from common_round1 import require
    from geometry import direct, supports, top_two
    from vendor import constrained_onboarding_core_v3 as core, p4_worker

    first = np.array([0, .25, .25, .1, .1, .25, np.inf])
    second = np.array([1, .75, .25, np.nextafter(1.,0.), 1.1, np.inf, np.inf])
    gate, a, b = supports(first, second, np.ones(len(first), dtype=bool))
    require(gate.tolist() == [False,True,True,True,False,False,False] and
            a[1] == .25 and b[1] == .5 and a[2] == b[2] == .75, 'STRICT_ONE_TIE_OR_SINGLE')
    require(not supports(first[:3], second[:3], np.zeros(3,bool))[0].any(), 'CLOSED_OR_MISSING_GEOMETRY')
    geom = dict(geometry={'protocols':{'6':dict(status='READY',rho_z=1.,rho_q=1.),
                '17':dict(status='NO_SOURCE_GEOMETRY_SUPPORT')}},
                context_radii={'6':dict(status='READY',rho_c=1.),'17':dict(status='NO_SOURCE_GEOMETRY_SUPPORT')})
    def row(uid, component, frame, use='REFERENCE', protocol=6):
        return dict(uid=uid,device='fixture',partition='DEV',component_id=component,capture_id='cap',
                    protocol=protocol,frame=frame,timestamp=1. if use=='REFERENCE' else 3.,
                    label=0,use=use,reference_end=2.,bank_end_frame=5)
    rr = [row('a','X',1),row('b','X',2),row('c','Y',3),row('d','Z',4),row('e','U',5,protocol=17)]
    qr = [row('q1','Q',6,'QUERY'),row('q2','Q',5,'QUERY'),row('q3','Q',7,'QUERY',17),
          dict(row('q4','Q',9,'QUERY'),timestamp=2.)]
    norms = np.zeros(768), np.ones(768)
    z = np.ones((len(rr),768))
    q = np.tile(np.array([.1,.2,.75,.3,.1])[:,None],(1,14))
    cx = np.tile(np.array([.1,.2,.1,.8,.1])[:,None],(1,8))
    bank = core.ReferenceBank(rr,z,q,norms,feature_uids=[r['uid'] for r in rr],q_uids=[r['uid'] for r in rr])
    qz = np.ones((len(qr),768))
    sq, sx = np.zeros((len(qr),14)), np.zeros((len(qr),8))
    g = top_two(qr,qz,sq,sx,bank,cx,geom,lambda *args,**kwargs: None)
    direct(qr,qz,sq,sx,bank,cx,geom,g)
    require(np.allclose(g['m'][0], [.1,.75]) and g['donors'][0].tolist() == [0,2]
            and g['gate'].tolist() == [True,False,False,False], 'MINIMIZE_JOINT_WITHIN_DISTINCT_COMPONENT')
    geom['geometry']['protocols']['17'] = geom['geometry']['protocols']['6']
    geom['context_radii']['17'] = geom['context_radii']['6'].copy()
    single = top_two(qr,qz,sq,sx,bank,cx,geom,lambda *args,**kwargs: None)
    require(single['m'][2,0] < 1 and np.isinf(single['m'][2,1]) and
            not single['gate'][2] and single['weak'][2] == single['mean'][2] == 0, 'ONE_COMPATIBLE_COMPONENT')
    geom['context_radii']['6']['rho_c'] = 0.
    empty = top_two(qr,qz,sq,sx,bank,cx,geom,lambda *args,**kwargs: None)
    require(not empty['gate'].any() and not empty['mean'].any(), 'ZERO_RADIUS_HANDLING')
    raw = np.ones((2,4))
    flags = np.zeros((2,14))
    flags[1,[0,2]] = 1
    scored = p4_worker.correct(raw,np.full(2,.5),flags,[4.,4.,4.],True,power=4)
    require(np.array_equal(scored[1],raw[1]) and np.all(scored[0] == 1.-(1.-.5**4))
            and scored[0,0] != (.75**4+.25**4)/2, 'APPLY_G4_AFTER_MEAN_AND_BYPASS')
    return dict(status='PASS', cases=['strict_m2_equal_one','m2_immediately_below_one','missing_geometry',
                'time_and_frame_boundaries','one_component','same_component_duplicates','equal_minima',
                'joint_before_component_ranking','zero_radius','g4_after_mean','protocol_bypass'])
