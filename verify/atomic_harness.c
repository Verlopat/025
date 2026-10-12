/* Bounded C11-atomic client for GenMC (RC11/SC) and Nidhugg (SC/TSO).
 * Do not interpret GenMC RC11 as TSO. No randomized inputs, finite loops.
 * This C transcription is separately compiled and is not a proof of C++ source identity.
 */
#include <stdatomic.h>
#include <pthread.h>
#include <stdint.h>
#include <assert.h>

static _Atomic uint64_t parent[3];
static uint32_t get_parent(uint64_t w){return (uint32_t)w;}
static uint32_t get_version(uint64_t w){return (uint32_t)(w>>32);}
static uint64_t make_word(uint32_t p,uint32_t v){return ((uint64_t)v<<32)|p;}
static uint32_t root(uint32_t x){
    for(int i=0;i<4;i++){
        uint32_t p=get_parent(atomic_load_explicit(&parent[x],memory_order_acquire));
        if(p==x)return x;
        assert(p<x);
        x=p;
    }
    assert(0 && "bounded find traversal exceeded 3 elements");
    return 0;
}
static int join(uint32_t x,uint32_t y){
    for(int j=0;j<8;j++){
        uint32_t a=root(x),b=root(y);
        if(a==b)return 0;
        uint32_t high=a>b?a:b,low=a>b?b:a;
        uint64_t expected=atomic_load_explicit(&parent[high],memory_order_acquire);
        if(get_parent(expected)!=high)continue;
        assert(get_version(expected)<UINT32_MAX);
        uint64_t desired=make_word(low,get_version(expected)+1);
        if(atomic_compare_exchange_strong_explicit(&parent[high],&expected,desired,
            memory_order_acq_rel,memory_order_acquire))return 1;
    }
    // Reaching a bound is inconclusive, not evidence of incorrect progress.
    return -1;
}
static void* thread_a(void* ignored){ (void)ignored; assert(join(2,1)>=0); return 0; }
static void* thread_b(void* ignored){ (void)ignored; assert(join(2,0)>=0); return 0; }
int main(void){
    for(uint32_t i=0;i<3;i++)atomic_init(&parent[i],make_word(i,0));
    pthread_t a,b;
    assert(pthread_create(&a,0,thread_a,0)==0);
    assert(pthread_create(&b,0,thread_b,0)==0);
    pthread_join(a,0);pthread_join(b,0);
    for(uint32_t i=0;i<3;i++){
        uint32_t p=get_parent(atomic_load_explicit(&parent[i],memory_order_acquire));
        assert(p<=i);
    }
    assert(root(0)==root(1) && root(1)==root(2));
    return 0;
}
