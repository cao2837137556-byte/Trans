"""Five fixed proposal rounds; source-guarded replay, never CAL-selected endpoints."""
import time
import numpy as np
import torch
import risk_core as r
import guard_core as g

def run(model,opt,x,zx,teacher,teacher_zero,sy,sw,upper,scale,seed,small,spec,folder,p,c,guard,evaluate):
    rng=np.random.default_rng(seed);epochs=1 if small else 5;batches=8 if small else 64
    previous=guard.evaluate(guard.base,guard.zero_base);assert all(previous['checks'].values())
    initial=previous;count=0;accepted_count=0;records=[];trajectory=[];first_normal_norm=None
    start=time.monotonic()
    for epoch in range(epochs):
        order=[rng.permutation(np.flatnonzero(sy==y)) for y in (0,1)]
        batch_indices=[np.r_[order[0][b*128:(b+1)*128],order[1][b*128:(b+1)*128]] for b in range(batches)]
        def train(limit=batches):
            nonlocal count,first_normal_norm
            losses=[];model.train()
            for b,ix in enumerate(batch_indices[:limit]):
                opt.zero_grad(set_to_none=True)
                s=model(x[ix]).flatten();z=model(zx[ix]).flatten()
                terms=r.components(s,z,teacher[ix],teacher_zero[ix],torch.from_numpy(sy[ix]),sw[ix],upper,scale,8192)
                protection=10*(terms[1]+terms[2]);loss=terms[0]+protection;assert torch.isfinite(loss)
                if b in (0,31,63):
                    a=r.vector(terms[0],model);v=r.vector(protection,model)
                    if first_normal_norm is None:first_normal_norm=float(torch.linalg.vector_norm(a))
                    records.append(dict(round=epoch+1,batch=b+1,executed_before=count,relation=r.relation(a,v),losses=[float(t.detach()) for t in terms]))
                loss.backward();assert all(v.grad is not None and torch.isfinite(v.grad).all() for v in model.parameters())
                opt.step();assert all(torch.isfinite(v).all() for v in model.parameters())
                count+=1;losses.append([float(t.detach()) for t in terms]+[float(loss.detach())])
                p.optimizer_updates=count;p.stage='GUARDED_PROPOSAL_seed'+str(seed)+'_round'+str(epoch+1);p.tick(b+1,batches)
            return dict(updates=limit,loss_means=np.mean(losses,axis=0).tolist())
        result=g.guarded_block(model,opt,train,evaluate,previous,spec['learning_rate'],tuple(spec['guard']['lr_factors']))
        previous=result['evidence'];assert all(previous['checks'].values())
        if result['accepted']:accepted_count+=batches
        result.update(round=epoch+1,nominal_updates=(epoch+1)*batches,executed_updates=count,retained_optimizer_updates=accepted_count)
        trajectory.append(result)
        c.save_arrays(folder/f'epoch_{epoch+1:02d}.npz',**{n:v.detach().numpy() for n,v in model.state_dict().items()})
        c.write(folder/f'round_{epoch+1:02d}_GUARD.json',result,replace=True)
    rollback_smoke=None
    if small:
        # A real one-batch proposal in every retry slot must leave no weight,
        # moment, step-counter or RNG changes after all four forced rejections.
        before=g.state_hash(g.snapshot(model,opt));before_count=count
        def reject():return dict(checks={'forced_runtime_negative_control':False},normal_tail_risk=previous['normal_tail_risk'])
        smoke=g.guarded_block(model,opt,lambda:train(1),reject,previous,spec['learning_rate'])
        assert not smoke['accepted'] and g.state_hash(g.snapshot(model,opt))==before
        rollback_smoke=dict(status='PASS',forced_rejected_attempts=4,actual_optimizer_steps=count-before_count,complete_state_restored=True)
    seconds=time.monotonic()-start
    risk_gain=(initial['normal_tail_risk']-previous['normal_tail_risk'])/max(initial['normal_tail_risk'],1e-30)
    worst_epoch=max(a['train_seconds']*(64/batches)+a['guard_seconds'] for v in trajectory for a in v['attempts'])
    return dict(epochs=epochs,nominal_updates=epochs*batches,executed_updates=count,retained_optimizer_updates=accepted_count,
        rejected_attempts=sum(not a['accepted'] for v in trajectory for a in v['attempts']),
        accepted_rounds=sum(v['accepted'] for v in trajectory),trajectory=trajectory,gradient_probes=records,
        first_normal_gradient_norm=first_normal_norm,train_seconds=seconds,rollback_smoke=rollback_smoke,
        initial_source_guard=initial,final_source_guard=previous,normal_tail_risk_relative_reduction=risk_gain,
        signal_ready=accepted_count>0 and first_normal_norm>1e-12 and risk_gain>1e-8,
        worst_single_attempt_formal_epoch_seconds=worst_epoch)
