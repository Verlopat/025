#pragma once
#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <algorithm>

namespace saw {
struct Metrics {
    uint64_t loads = 0, cas = 0, failed = 0, splits = 0, hops = 0;
    void add(const Metrics& x) { loads+=x.loads; cas+=x.cas; failed+=x.failed; splits+=x.splits; hops+=x.hops; }
};
// one 64-bit atomic per element; version excludes wraparound by checked precondition.
constexpr uint64_t pack(uint32_t parent, uint32_t version) {
    return (uint64_t(version) << 32) | parent;
}
constexpr uint32_t parent_of(uint64_t w) { return uint32_t(w); }
constexpr uint32_t version_of(uint64_t w) { return uint32_t(w >> 32); }
struct PauseConfig {
    std::string hook = "none";
    uint32_t micros = 0, percent = 0;
    uint64_t seed = 0;
};
class DSU {
public:
    explicit DSU(uint32_t n) : n_(n) { if (!n) throw std::invalid_argument("n must be positive"); }
    virtual ~DSU() = default;
    virtual uint32_t find(uint32_t x, Metrics& m) = 0;
    virtual bool unite(uint32_t x, uint32_t y, Metrics& m) = 0;
    virtual uint32_t raw_parent(uint32_t x) const = 0;
    uint32_t size() const { return n_; }
    void check(uint32_t x) const { if (x >= n_) throw std::out_of_range("element outside universe"); }
protected:
    uint32_t n_;
};
class Sequential final : public DSU {
    std::vector<uint32_t> p_, sizes_;
public:
    explicit Sequential(uint32_t n) : DSU(n), p_(n), sizes_(n,1) {
        for (uint32_t i=0;i<n;++i) p_[i]=i;
    }
    uint32_t find(uint32_t x, Metrics& m) override {
        check(x); uint32_t root=x;
        while (p_[root]!=root) { root=p_[root]; ++m.loads; ++m.hops; }
        ++m.loads;
        while (p_[x]!=x) { uint32_t next=p_[x]; p_[x]=root; x=next; }
        return root;
    }
    bool unite(uint32_t x,uint32_t y,Metrics& m) override {
        auto a=find(x,m), b=find(y,m); if(a==b) return false;
        if(sizes_[a]<sizes_[b] || (sizes_[a]==sizes_[b] && a>b)) std::swap(a,b);
        p_[b]=a; sizes_[a]+=sizes_[b]; return true;
    }
    uint32_t raw_parent(uint32_t x) const override { check(x); return p_[x]; }
};
class MutexDSU final : public DSU {
    mutable std::mutex mutex_;
    std::vector<uint32_t> p_, sizes_;
    uint32_t root(uint32_t x, Metrics& m) {
        while(p_[x]!=x){ x=p_[x]; ++m.hops; ++m.loads; }
        ++m.loads; return x;
    }
public:
    explicit MutexDSU(uint32_t n):DSU(n),p_(n),sizes_(n,1){ for(uint32_t i=0;i<n;++i)p_[i]=i; }
    uint32_t find(uint32_t x,Metrics& m) override { check(x); std::lock_guard<std::mutex> guard(mutex_); return root(x,m); }
    bool unite(uint32_t x,uint32_t y,Metrics& m) override {
        check(x); check(y); std::lock_guard<std::mutex> guard(mutex_);
        auto a=root(x,m),b=root(y,m); if(a==b)return false;
        if(sizes_[a]<sizes_[b] || (sizes_[a]==sizes_[b] && a>b)) std::swap(a,b);
        p_[b]=a; sizes_[a]+=sizes_[b]; return true;
    }
    uint32_t raw_parent(uint32_t x) const override { check(x); std::lock_guard<std::mutex> guard(mutex_); return p_[x]; }
};
// Root-ID monotonic linking. Compare atomic root word immediately before committing.
// Atomic algorithms do not use a global lock; base, SC, relaxed and splitting variants.
class AtomicDSU final : public DSU {
    std::unique_ptr<std::atomic<uint64_t>[]> p_;
    bool versioned_, sequential_, splitting_, relaxed_;
    PauseConfig pause_;
    std::memory_order load_order() const { return sequential_ ? std::memory_order_seq_cst : relaxed_ ? std::memory_order_relaxed : std::memory_order_acquire; }
    std::memory_order success_order() const { return sequential_ ? std::memory_order_seq_cst : relaxed_ ? std::memory_order_relaxed : std::memory_order_acq_rel; }
    std::memory_order failure_order() const { return sequential_ ? std::memory_order_seq_cst : relaxed_ ? std::memory_order_relaxed : std::memory_order_acquire; }
    // Deterministic hook selection keyed to operation context rather than scheduler timing.
    void maybe_pause(const std::string& at, uint64_t token) const {
        if(pause_.hook != at || pause_.micros==0 || pause_.percent==0) return;
        uint64_t k = (token ^ pause_.seed) + 0x9e3779b97f4a7c15ULL;
        k = (k ^ (k >> 30)) * 0xbf58476d1ce4e5b9ULL;
        k = (k ^ (k >> 27)) * 0x94d049bb133111ebULL;
        k ^= k >> 31;
        if(k % 100 < pause_.percent) std::this_thread::sleep_for(std::chrono::microseconds(pause_.micros));
    }
    uint64_t next_word(uint32_t newparent,uint32_t version) const {
        if(!versioned_) return pack(newparent,0);
        if(version == UINT32_MAX) throw std::overflow_error("version counter overflow");
        return pack(newparent,version+1);
    }
public:
    AtomicDSU(uint32_t n, const std::string& variant, PauseConfig pause={})
      :DSU(n),p_(std::make_unique<std::atomic<uint64_t>[]>(n)),
       versioned_(variant!="b3" && variant!="a1"),
       sequential_(variant=="b4"),splitting_(variant=="a3"),
       relaxed_(variant=="a2"),pause_(std::move(pause)) {
       for(uint32_t i=0;i<n;++i)p_[i].store(pack(i,0),std::memory_order_relaxed);
    }
    uint32_t find(uint32_t x, Metrics& m) override {
        check(x); auto current=x;
        for(;;) {
            const uint64_t w=p_[current].load(load_order()); ++m.loads;
            const uint32_t par=parent_of(w);
            if(par==current)return current;
            if(par >= current || par>=n_)throw std::logic_error("monotonicity violated");
            if(splitting_) {
                const uint64_t next=p_[par].load(load_order()); ++m.loads;
                uint32_t grand=parent_of(next);
                if(grand<par) {
                    auto expected=w;
                    ++m.cas; ++m.splits;
                    if(!p_[current].compare_exchange_strong(expected,
                          next_word(grand,version_of(w)),success_order(),failure_order()))++m.failed;
                }
            }
            current=par; ++m.hops;
        }
    }
    bool unite(uint32_t x,uint32_t y,Metrics& m) override {
        check(x);check(y);
        uint64_t attempt=0;
        for(;;) {
            const uint32_t a=find(x,m), b=find(y,m);
            maybe_pause("after_root", ((uint64_t(x)<<32)|y) ^ attempt);
            if(a==b) return false;
            uint32_t hi=std::max(a,b),lo=std::min(a,b);
            uint64_t old=p_[hi].load(load_order()); ++m.loads;
            if(parent_of(old)!=hi) { ++m.failed; ++attempt; continue; }
            maybe_pause("before_cas", ((uint64_t(hi)<<32)|lo) ^ attempt);
            auto expected=old; ++m.cas;
            if(p_[hi].compare_exchange_strong(expected,next_word(lo,version_of(old)),
                success_order(),failure_order()))return true;
            ++m.failed; ++attempt;
            maybe_pause("after_failure", ((uint64_t(hi)<<32)|lo) ^ attempt);
        }
    }
    uint32_t raw_parent(uint32_t x) const override { check(x); return parent_of(p_[x].load(std::memory_order_acquire)); }
    uint64_t raw_word(uint32_t x) const { check(x); return p_[x].load(std::memory_order_acquire); }
};
inline std::unique_ptr<DSU> make_dsu(uint32_t n,const std::string& variant,PauseConfig pause={}) {
    if(variant=="b1") return std::make_unique<Sequential>(n);
    if(variant=="b2") return std::make_unique<MutexDSU>(n);
    if(variant=="p1"||variant=="b3"||variant=="b4"||variant=="a1"||variant=="a2"||variant=="a3")
        return std::make_unique<AtomicDSU>(n,variant,pause);
    throw std::invalid_argument("unknown variant: "+variant);
}
inline bool invariant(const DSU& d) {
    // Validates a quiescent snapshot in O(n), not once-per-node O(depth).
    const bool must_decrease = dynamic_cast<const AtomicDSU*>(&d) != nullptr;
    std::vector<uint8_t> mark(d.size(),0);
    std::vector<uint32_t> chain;
    for(uint32_t i=0;i<d.size();++i) {
        if(mark[i]==2)continue;
        chain.clear();uint32_t x=i;
        while(mark[x]!=2) {
            if(mark[x]==1)return false; // cycle
            mark[x]=1;chain.push_back(x);
            uint32_t p=d.raw_parent(x);
            if(p>=d.size() || (must_decrease && p>x))return false;
            if(p==x)break;
            x=p;
        }
        for(auto v:chain)mark[v]=2;
    }
    return true;
}

} // namespace saw
