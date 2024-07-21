// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./InterfaceSimples.sol";

abstract contract ContratoSimplesStandaloneV2 is InterfaceSimples {
    uint256 data;

    function set(uint256 _data) override external {
        data = _data;
    }

    function get() override external view returns (uint256) {
        return data;
    }
}
