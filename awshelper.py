import boto3

_clients = {}
_functions = {}
_session = None


# the last two keys should both be None or both be non-None
def _get_client(client_type, region):
    if _session is None:
        raise ValueError("Session has not been initialized")
    return _session.client(client_type, region_name=region)


def _aws_response(response_func, args_dict):
    response = response_func(**args_dict)
    metadata = response["ResponseMetadata"]
    if "HTTPStatusCode" not in metadata or metadata["HTTPStatusCode"] != 200:
        raise IOError("Unexpected status code " + metadata.get("HTTPStatusCode", None))
    response.pop("ResponseMetadata")
    return response


def aws_get_config(region):
    config = {}
    for key in _functions[region]:
        (response_func, args_dict) = _functions[region][key]
        try:
            response = _aws_response(response_func, args_dict)
        except Exception as e:
            print("Exception getting {} for {}: {}".format(key, region, e))
            continue
        config[key] = response
        if key == "TransitGatewayRouteTables":
            _aws_get_route_table_details(_clients[region]["ec2"], config, response["TransitGatewayRouteTables"])
        if key == "LoadBalancers":
            _aws_get_load_balancer_details(_clients[region]["elbv2"], config, response["LoadBalancers"])
        if key == "TargetGroups":
            _aws_get_elbv2_target_health(_clients[region]["elbv2"], config, response["TargetGroups"])
    return config


import json


def _aws_get_load_balancer_details(client, config, load_balancers):
    listeners = []
    attributes = []
    for load_balancer in load_balancers:
        lb_arn = load_balancer["LoadBalancerArn"]
        try:
            response = _aws_response(client.describe_listeners, dict(LoadBalancerArn=lb_arn))
            response["LoadBalancerArn"] = lb_arn
            listeners.append(response)
        except Exception as e:
            print(
                "Exception getting load balancer listeners for {} with arn {}: {}".format(
                    load_balancer["LoadBalancerName"],
                    lb_arn, e))

        try:
            response = _aws_response(client.describe_load_balancer_attributes, dict(LoadBalancerArn=lb_arn))
            response["LoadBalancerArn"] = lb_arn
            attributes.append(response)
        except Exception as e:
            print(
                "Exception getting load balancer attributes for {} with arn {}: {}".format(
                    load_balancer["LoadBalancerName"],
                    lb_arn, e))

    config["LoadBalancerListeners"] = {"LoadBalancerListeners": listeners}
    config["LoadBalancerAttributes"] = {"LoadBalancerAttributes" : attributes}


def _aws_get_elbv2_target_health(client, config, target_groups):
    healths = []
    for target_group in target_groups:
        tg_arn = target_group["TargetGroupArn"]
        try:
            response = _aws_response(client.describe_target_health, dict(TargetGroupArn=tg_arn))
            response["TargetGroupArn"] = tg_arn
            healths.append(response)
        except Exception as e:
            print(
                "Exception getting target health for target group {} with Arn {}: {}".format(
                    target_group["TargetGroupName"], tg_arn, e))

    config["LoadBalancerTargetHealth"] = {"LoadBalancerTargetHealth": healths}


def _aws_get_route_table_details(client, config, route_tables):
    static_routes = []
    propogations = []
    for table in route_tables:
        table_id = table["TransitGatewayRouteTableId"]

        try:
            propogations_response = _aws_response(client.get_transit_gateway_route_table_propagations,
                                                  dict(TransitGatewayRouteTableId=table_id))
            propogations_response["TransitGatewayRouteTableId"] = table_id
            propogations.append(propogations_response)
        except Exception as e:
            print("Exception getting Propagations for {}: {}".format(table_id, e))

        try:
            static_routes_response = _aws_response(client.search_transit_gateway_routes,
                                                   dict(TransitGatewayRouteTableId=table_id,
                                                        Filters=[{"Name": "type", "Values": ["static"]}]))
            if static_routes_response['AdditionalRoutesAvailable']:
                raise IOError("Could not fetch all static routes for " + table_id)
            static_routes_response["TransitGatewayRouteTableId"] = table_id
            static_routes.append(static_routes_response)
        except Exception as e:
            print("Exception getting Static routes for {}: {}".format(table_id, e))

    config["TransitGatewayPropagations"] = {"TransitGatewayPropagations": propogations}
    config["TransitGatewayStaticRoutes"] = {"TransitGatewayStaticRoutes": static_routes}


def aws_get_regions():
    return _clients.keys()


def aws_init(regions=None, vpc_ids=None, skip_data=None, profile=None):
    global _session, _clients, _functions

    _session = boto3.session.Session(profile_name=profile)

    if regions is None or len(regions) == 0:
        ec2_client = _get_client('ec2', "us-west-1")
        response = ec2_client.describe_regions()
        regions_to_get = [region["RegionName"] for region in response["Regions"]]
    else:
        regions_to_get = regions

    if vpc_ids is None or len(vpc_ids) == 0:
        vpc_filter = []
        attachment_vpc_filter = []
    else:
        vpc_filter = [{'Name': "vpc-id", 'Values': vpc_ids}]
        attachment_vpc_filter = [{'Name': "attachment.vpc-id", 'Values': vpc_ids}]

    for region in regions_to_get:
        _clients[region] = {}

        ec2_client = _get_client("ec2", region)
        _clients[region]["ec2"] = ec2_client

        _functions[region] = {}
        _functions[region]["Addresses"] = (ec2_client.describe_addresses, dict())
        _functions[region]["AvailabilityZones"] = (ec2_client.describe_availability_zones, dict())
        _functions[region]["ClassicLinkInstances"] = (
            ec2_client.describe_classic_link_instances, dict(Filters=vpc_filter))
        _functions[region]["CustomerGateways"] = (ec2_client.describe_customer_gateways, dict())
        _functions[region]["DhcpOptions"] = (ec2_client.describe_dhcp_options, dict())
        _functions[region]["Hosts"] = (ec2_client.describe_hosts, dict())
        _functions[region]["InstanceStatuses"] = (ec2_client.describe_instance_status, dict())
        _functions[region]["InternetGateways"] = (
            ec2_client.describe_internet_gateways, dict(Filters=attachment_vpc_filter))
        _functions[region]["MovingAddressStatuses"] = (ec2_client.describe_moving_addresses, dict())
        _functions[region]["NatGateways"] = (ec2_client.describe_nat_gateways, dict(Filters=vpc_filter))
        _functions[region]["NetworkAcls"] = (ec2_client.describe_network_acls, dict(Filters=vpc_filter))
        _functions[region]["NetworkInterfaces"] = (ec2_client.describe_network_interfaces, dict(Filters=vpc_filter))
        _functions[region]["PlacementGroups"] = (ec2_client.describe_placement_groups, dict())
        _functions[region]["PrefixLists"] = (ec2_client.describe_prefix_lists, dict())
        _functions[region]["Reservations"] = (ec2_client.describe_instances, dict(Filters=vpc_filter))
        _functions[region]["RouteTables"] = (ec2_client.describe_route_tables, dict(Filters=vpc_filter))
        _functions[region]["SecurityGroups"] = (ec2_client.describe_security_groups, dict(Filters=vpc_filter))
        _functions[region]["Subnets"] = (ec2_client.describe_subnets, dict(Filters=vpc_filter))
        _functions[region]["Tags"] = (ec2_client.describe_tags, dict())
        _functions[region]["TransitGatewayAttachments"] = (ec2_client.describe_transit_gateway_attachments, dict())
        _functions[region]["TransitGatewayRouteTables"] = (ec2_client.describe_transit_gateway_route_tables, dict())
        _functions[region]["TransitGatewayVpcAttachments"] = (
            ec2_client.describe_transit_gateway_vpc_attachments, dict(Filters=vpc_filter))
        _functions[region]["TransitGateways"] = (ec2_client.describe_transit_gateways, dict())
        _functions[region]["VpcEndpoints"] = (ec2_client.describe_vpc_endpoints, dict(Filters=vpc_filter))
        _functions[region]["VpcPeeringConnections"] = (ec2_client.describe_vpc_peering_connections, dict())
        _functions[region]["Vpcs"] = (ec2_client.describe_vpcs, dict(Filters=vpc_filter))
        _functions[region]["VpcClassicLink"] = (ec2_client.describe_vpc_classic_link, dict())
        _functions[region]["VpcClassicLinkDnsSupport"] = (ec2_client.describe_vpc_classic_link_dns_support, dict())
        _functions[region]["VpcEndpointServices"] = (ec2_client.describe_vpc_endpoint_services, dict())
        _functions[region]["VpnConnections"] = (ec2_client.describe_vpn_connections, dict())
        _functions[region]["VpnGateways"] = (ec2_client.describe_vpn_gateways, dict(Filters=attachment_vpc_filter))

        # get all elasticsearch domain names for this account (VPC based filtering is not supported yet)
        es_client = _get_client('es', region)
        _clients[region]["es"] = es_client
        domain_names = es_client.list_domain_names()
        _functions[region]["ElasticsearchDomains"] = (es_client.describe_elasticsearch_domains, dict(
            DomainNames=[domainEntry["DomainName"] for domainEntry in domain_names["DomainNames"]]))

        # get all RDS instances (VPC based filtering is not supported yet)
        rds_client = _get_client('rds', region)
        _clients[region]["rds"] = rds_client
        _functions[region]["RdsInstances"] = (rds_client.describe_db_instances, dict())

        elbv2_client = _get_client('elbv2', region)
        _clients[region]["elbv2"] = elbv2_client
        _functions[region]["LoadBalancers"] = (elbv2_client.describe_load_balancers, dict())
        _functions[region]["TargetGroups"] = (elbv2_client.describe_target_groups, dict())

        if skip_data is not None:
            for key in skip_data:
                _functions[region].pop(key)


def aws_test_access(profile=None):
    try:
        session = boto3.session.Session(profile_name=profile)
        client = session.client("ec2", "us-west-1")
        client.describe_regions()
        print("You have access to AWS!\n")
    except Exception as e:
        print("You may not have access. Exception while accessing AWS: {}".format(e))
