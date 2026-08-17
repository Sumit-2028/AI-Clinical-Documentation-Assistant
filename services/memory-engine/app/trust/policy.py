from contracts.schemas import MemorySource, TrustTier


def initial_trust_tier(source: MemorySource) -> TrustTier:
    if source in {
        MemorySource.SIMULATED_ABHA,
        MemorySource.PHYSICIAN_APPROVED_CONSULTATION,
    }:
        return TrustTier.VERIFIED
    return TrustTier.UNVERIFIED


def is_established(tier: TrustTier) -> bool:
    return tier in {TrustTier.VERIFIED, TrustTier.PHYSICIAN_REVIEWED}


class TrustTierPolicy:
    @staticmethod
    def initial_tier(source: MemorySource) -> TrustTier:
        return initial_trust_tier(source)

    @staticmethod
    def is_established(tier: TrustTier) -> bool:
        return is_established(tier)
